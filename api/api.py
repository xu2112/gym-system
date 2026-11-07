"""登入、註冊、登出，以及身分權限檢查。"""
from functools import wraps

import psycopg2
from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from api.sql import Account, Member, friendly_error

api = Blueprint('api', __name__, template_folder='./templates')

login_manager = LoginManager()
login_manager.login_view = 'api.login'
login_manager.login_message = '請先登入'


class User(UserMixin):
    def __init__(self, row):
        self.id = row['account']
        self.role = row['identity']      # 'manager' 或 'member'
        self.mid = row['mid']            # 管理者為 None
        self.name = row['name']


@login_manager.user_loader
def user_loader(account):
    row = Account.get(account)
    return User(row) if row else None


def role_required(role):
    """限制只有某種身分能進入，例如 @role_required('manager')。"""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role != role:
                flash('您沒有權限使用這個頁面。', 'warning')
                return redirect(home_url())
            return view(*args, **kwargs)
        return wrapper
    return decorator


def home_url():
    if current_user.is_authenticated and current_user.role == 'manager':
        return url_for('manager.dashboard')
    if current_user.is_authenticated:
        return url_for('member.courses')
    return url_for('index')


@api.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(home_url())
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        row = Account.get(account)
        if row is None or not check_password_hash(row['password'], password):
            flash('帳號或密碼錯誤，請再試一次。', 'danger')
            return render_template('login.html', account=account)
        login_user(User(row))
        return redirect(home_url())
    return render_template('login.html')


@api.route('/register', methods=['GET', 'POST'])
def register():
    """會員自行註冊：同時建立會員資料、電話與登入帳號。管理者帳號不開放註冊。"""
    form = request.form
    if request.method == 'POST':
        account = form.get('account', '').strip()
        password = form.get('password', '')
        error = None
        if len(account) < 3:
            error = '帳號至少需要 3 個字元。'
        elif len(password) < 4:
            error = '密碼至少需要 4 個字元。'
        elif password != form.get('password2', ''):
            error = '兩次輸入的密碼不一致。'
        elif Account.exists(account):
            error = '這個帳號已經有人使用。'
        if error is None:
            try:
                data = {
                    'mname': form['mname'].strip(),
                    'email': form['email'].strip() or None,
                    'sex': form['sex'],
                    'birthday': form['birthday'] or None,
                }
                Member.create(data, phone=form.get('phone', '').strip() or None,
                              account=account,
                              password_hash=generate_password_hash(password, method='pbkdf2:sha256:600000'))
                flash('註冊成功，請登入。', 'success')
                return redirect(url_for('api.login'))
            except psycopg2.Error as e:
                error = friendly_error(e)
        flash(error, 'danger')
    return render_template('register.html', form=form)


@api.route('/logout')
def logout():
    logout_user()
    flash('已登出。', 'success')
    return redirect(url_for('index'))
