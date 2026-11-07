import os

from dotenv import load_dotenv
from flask import Flask, render_template, redirect
from flask_login import current_user

from api.api import api, login_manager, home_url
from api.forms import LABELS, BADGES
from member.views.member import member
from backstage.views.manager import manager

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-secret-key')

app.register_blueprint(api, url_prefix='/')
app.register_blueprint(member, url_prefix='/member')
app.register_blueprint(manager, url_prefix='/backstage')
login_manager.init_app(app)


@app.template_filter('label')
def label_filter(code):
    """把資料庫裡的代碼（booked、approved…）轉成中文。"""
    return LABELS.get(code, code)


@app.template_filter('badge')
def badge_filter(code):
    return BADGES.get(code, 'secondary')


@app.template_filter('money')
def money_filter(value):
    return f'{value or 0:,.0f}'


@app.template_filter('hm')
def hm_filter(t):
    return t.strftime('%H:%M') if t else ''


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(home_url())
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
