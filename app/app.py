import os

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort, Blueprint
from flask_paginate import Pagination, get_page_parameter
from flask_sqlalchemy import SQLAlchemy
from flask_whooshee import Whooshee
from flask_bootstrap import Bootstrap

import click
from faker import Faker  
import chardet

try:
    from urlparse import urlparse, urljoin
except ImportError:
    from urllib.parse import urlparse, urljoin

fake = Faker()  

app = Flask(__name__)
# config
prefix = 'sqlite:///'
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(basedir, 'data.db')
app.config['SECRET_KEY'] = 'secret-key' 

db = SQLAlchemy(app)
whooshee = Whooshee(app)
bootstrap = Bootstrap(app)

# model
@whooshee.register_model('name', 'username', 'nickname')
class Info(db.Model):
    __tablename__ = 'info'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, index=True)
    email = db.Column(db.String(254), unique=True, index=True)
    password = db.Column(db.String(128))
    nickname = db.Column(db.String(50))
    name = db.Column(db.String(30))
    id_card = db.Column(db.String(18))
    phone = db.Column(db.String(11))


@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    """Initialize the database."""
    if drop:
        click.confirm('This operation will delete the database, do you want to continue?', abort=True)
        db.drop_all()
        click.echo('Drop tables.')
    db.create_all()
    click.echo('Initialized database.')


@app.cli.command()
@click.option('--filename', default='info.txt', help='Filename of infos, only for txt.')
def forge(filename):
    """Generate infos from a text file."""
    click.echo('Working...')

    # 读取文件的前几个字节来猜测编码
    with open(filename, 'rb') as f:  # 使用二进制模式打开文件
        rawdata = f.read(10000)  # 读取前10000个字节，这个数量可以根据需要调整
        result = chardet.detect(rawdata)
        encoding = result['encoding']

    print(f"Detected encoding: {encoding}")
    try:
        # 假设每行数据按照--分隔
        with open(filename, 'r', encoding=encoding) as file:
            lines = file.readlines()
            count = len(lines)

            for line in lines:
                parts = line.strip().split('----')  # 去除行尾空格，并按--分割
                if len(parts) != 7:  # 确保数据格式正确
                    click.echo(f"Invalid data format in line: {line}")
                    continue

                username, password, name, id_card, nickname, phone, email = parts

                info = Info(
                    username=username,  
                    email=email,
                    password=password,
                    nickname=nickname, 
                    name=name,
                    id_card=id_card,
                    phone=phone
                )
                existing_user = Info.query.filter_by(username=username).first()
                if existing_user:
                    click.echo(f"Skipping duplicate username: {username}")
                    continue

                # 如果没有重复，则添加到数据库
                db.session.add(info)

            db.session.commit()
            click.echo(f'Created {len(lines) - skipped_count} infos from the text file.')

    except Exception as e:
        click.echo(f"An error occurred: {e}")
        db.session.rollback()  # 同样，对于其他异常也进行回滚

    db.session.commit()
    click.echo(f'Created {count} infos from the text file.')

@app.route('/')
def index():
    # 分页展示评论列表
    page = request.args.get(get_page_parameter(), type=int, default=1)
    info = Info.query.order_by(Info.id)

    pagination = Pagination(page=page, total=info.count(), css_framework='bootstrap4')

    info = info.offset((page - 1) * 10).limit(10).all()

    return render_template('index.html', info=info, pagination=pagination)

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if q == '':
        flash('Enter keyword about name, username, nickname.', 'warning')
        return redirect(url_for('.index'))
    
    if len(q) < 3:
        # 如果长度不足 3，返回错误页面或错误消息
        abort(400, description="Search string must have at least 3 characters")

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = Info.query.whooshee_search(q).paginate(page, per_page)
    results = pagination.items
    return render_template('search.html', q=q, results=results, pagination=pagination)


@app.route('/user/<nickname>')
def user_index(nickname):
    user = Info.query.filter_by(nickname=nickname).first_or_404()
    return render_template('user/index.html', user=user)
