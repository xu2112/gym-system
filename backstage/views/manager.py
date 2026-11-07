"""管理者後台：資料分析、會員、教練、課程、方案、合約、退款審核。"""
from datetime import date

import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash

from api.api import role_required
from api.forms import field, fill, SEX_OPTIONS, PAYMENT_OPTIONS
from api.sql import (Account, Member, Trainer, Course, Plan, Contract, Refund, Analysis,
                     friendly_error)

manager = Blueprint('manager', __name__, template_folder='../templates')


def run(action, success):
    """執行一個資料庫動作，成功顯示 success，失敗顯示中文錯誤訊息。回傳是否成功。"""
    try:
        result = action()
    except psycopg2.Error as e:
        flash(friendly_error(e), 'danger')
        return False
    if result == 0:
        flash('沒有資料被更新，可能資料已不存在或不符合條件。', 'warning')
        return False
    flash(success, 'success')
    return True


def form_data(names):
    """取出表單欄位，空字串轉成 None（資料庫裡存 NULL）。"""
    return {n: (request.form.get(n, '').strip() or None) for n in names}


def render_form(title, fields, back_url, **kwargs):
    if request.method == 'POST':
        fill(fields, request.form)
    return render_template('form.html', title=title, fields=fields, back_url=back_url, **kwargs)


@manager.route('/')
@role_required('manager')
def home():
    return redirect(url_for('manager.dashboard'))


# ================================================================ 資料分析
@manager.route('/dashboard')
@role_required('manager')
def dashboard():
    cash = Analysis.monthly_cash_flow()
    popularity = Analysis.course_popularity()
    plans = Plan.list()
    trainers = Trainer.list()

    def num(v):
        return float(v) if v is not None else None

    charts = {  # 給 ECharts 畫圖用的資料（全部轉成一般數字）
        'cash': {'months': [r['month'] for r in cash],
                 'collected': [num(r['collected']) for r in cash],
                 'refunded': [num(r['refunded']) for r in cash],
                 'net': [num(r['net_cash_flow']) for r in cash]},
        'course': {'names': [r['coname'] for r in popularity],
                   'occupancy': [num(r['occupancy_pct']) for r in popularity],
                   'attendance': [num(r['attendance_pct']) for r in popularity]},
        'plan': [{'name': p['pname'], 'value': num(p['net_collected'])} for p in plans],
        'trainer': {'names': [t['tname'] for t in trainers],
                    'members': [t['member_count'] for t in trainers],
                    'courses': [t['course_count'] for t in trainers]},
    }
    return render_template('admin_dashboard.html', overview=Analysis.overview(), charts=charts,
                           popularity=popularity, expiring=Contract.expiring(7))


# ================================================================ 會員
def member_fields(m=None, with_account=False):
    m = m or {}
    fields = [
        field('mname', '姓名', value=m.get('mname'), maxlength=50),
        field('email', 'Email', 'email', m.get('email'), maxlength=100),
        field('sex', '性別', 'select', m.get('sex'), options=SEX_OPTIONS),
        field('birthday', '生日', 'date', m.get('birthday')),
    ]
    if with_account:
        fields += [
            field('phone', '手機', required=False, maxlength=20),
            field('account', '登入帳號（不填就不建立帳號）', required=False, maxlength=30),
            field('password', '登入密碼', 'password', required=False),
        ]
    return fields


@manager.route('/members', methods=['GET', 'POST'])
@role_required('manager')
def members():
    if request.method == 'POST' and request.form.get('action') == 'delete':
        mid = request.form.get('mid')
        run(lambda: Member.delete(mid), f'已刪除會員 {mid}。')
        return redirect(url_for('manager.members'))
    keyword = request.args.get('keyword', '').strip()
    return render_template('admin_members.html', members=Member.list(keyword or None), keyword=keyword)


@manager.route('/members/new', methods=['GET', 'POST'])
@role_required('manager')
def members_new():
    if request.method == 'POST':
        data = form_data(['mname', 'email', 'sex', 'birthday', 'phone', 'account'])
        password = request.form.get('password', '')
        if data['account'] and Account.exists(data['account']):
            flash('這個登入帳號已經有人使用。', 'warning')
        elif data['account'] and len(password) < 4:
            flash('建立登入帳號時，密碼至少需要 4 個字元。', 'warning')
        else:
            try:
                mid = Member.create(data, phone=data['phone'], account=data['account'],
                                    password_hash=generate_password_hash(password, method='pbkdf2:sha256:600000')
                                    if data['account'] else None)
                flash(f'已新增會員 {mid}。', 'success')
                return redirect(url_for('manager.members'))
            except psycopg2.Error as e:
                flash(friendly_error(e), 'danger')
    return render_form('新增會員', member_fields(with_account=True), url_for('manager.members'), submit='新增')


@manager.route('/members/<mid>', methods=['GET', 'POST'])
@role_required('manager')
def members_edit(mid):
    m = Member.get(mid)
    if m is None:
        flash('找不到這位會員。', 'warning')
        return redirect(url_for('manager.members'))
    if request.method == 'POST':
        action = request.form.get('action', 'update')
        if action == 'add_phone':
            phone = request.form.get('phone', '').strip()
            run(lambda: Member.add_phone(mid, phone), f'已新增電話 {phone}。')
            return redirect(url_for('manager.members_edit', mid=mid))
        if action == 'delete_phone':
            phone = request.form.get('phone')
            run(lambda: Member.delete_phone(mid, phone), f'已刪除電話 {phone}。')
            return redirect(url_for('manager.members_edit', mid=mid))
        data = form_data(['mname', 'email', 'sex', 'birthday'])
        if run(lambda: Member.update(mid, data), f'已更新會員 {mid}。'):
            return redirect(url_for('manager.members'))
    acct = Account.of_member(mid)
    return render_form(f'編輯會員 {mid}', member_fields(m), url_for('manager.members'),
                       note=f'登入帳號：{acct["account"] if acct else "（無）"}',
                       extra_template='admin_member_phones.html', phones=Member.phones(mid), mid=mid)


# ================================================================ 教練
def trainer_fields(t=None, exclude=None):
    t = t or {}
    leaders = [(o['tid'], f"{o['tid']} {o['tname']}") for o in Trainer.options() if o['tid'] != exclude]
    return [
        field('tname', '姓名', value=t.get('tname'), maxlength=50),
        field('tphone', '電話', value=t.get('tphone'), required=False, maxlength=20),
        field('speciality', '專長', value=t.get('speciality'), required=False, maxlength=100),
        field('history', '經歷', 'textarea', t.get('history'), required=False),
        field('leader', '直屬主管', 'select', t.get('leader'), required=False, options=leaders),
    ]


TRAINER_COLUMNS = ['tname', 'tphone', 'speciality', 'history', 'leader']


@manager.route('/trainers', methods=['GET', 'POST'])
@role_required('manager')
def trainers():
    if request.method == 'POST' and request.form.get('action') == 'delete':
        tid = request.form.get('tid')
        run(lambda: Trainer.delete(tid), f'已刪除教練 {tid}。')
        return redirect(url_for('manager.trainers'))
    return render_template('admin_trainers.html', trainers=Trainer.list())


@manager.route('/trainers/new', methods=['GET', 'POST'])
@role_required('manager')
def trainers_new():
    if request.method == 'POST':
        data = form_data(TRAINER_COLUMNS)
        try:
            tid = Trainer.create(data)
            flash(f'已新增教練 {tid}。', 'success')
            return redirect(url_for('manager.trainers'))
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
    return render_form('新增教練', trainer_fields(), url_for('manager.trainers'), submit='新增')


@manager.route('/trainers/<tid>/edit', methods=['GET', 'POST'])
@role_required('manager')
def trainers_edit(tid):
    t = Trainer.get(tid)
    if t is None:
        flash('找不到這位教練。', 'warning')
        return redirect(url_for('manager.trainers'))
    if request.method == 'POST':
        data = form_data(TRAINER_COLUMNS)
        if run(lambda: Trainer.update(tid, data), f'已更新教練 {tid}。'):
            return redirect(url_for('manager.trainers'))
    return render_form(f'編輯教練 {tid}', trainer_fields(t, exclude=tid), url_for('manager.trainers'))


@manager.route('/trainers/<tid>', methods=['GET', 'POST'])
@role_required('manager')
def trainers_detail(tid):
    t = Trainer.get(tid)
    if t is None:
        flash('找不到這位教練。', 'warning')
        return redirect(url_for('manager.trainers'))
    if request.method == 'POST':
        mid = request.form.get('mid')
        if request.form.get('action') == 'assign':
            run(lambda: Trainer.assign(tid, mid), f'已將會員 {mid} 分派給 {t["tname"]}。')
        else:
            run(lambda: Trainer.unassign(tid, mid), f'已解除會員 {mid} 的分派。')
        return redirect(url_for('manager.trainers_detail', tid=tid))
    assigned = Trainer.members(tid)
    assigned_ids = {m['mid'] for m in assigned}
    others = [m for m in Member.options() if m['mid'] not in assigned_ids]
    return render_template('admin_trainer_detail.html', t=t, members=assigned, others=others)


# ================================================================ 課程
COURSE_COLUMNS = ['coname', 'capacity', 'location', 'codate', 'starttime', 'endtime', 'tid']


def course_fields(c=None):
    c = c or {}
    trainers = [(o['tid'], f"{o['tid']} {o['tname']}") for o in Trainer.options()]
    return [
        field('coname', '課程名稱', value=c.get('coname'), maxlength=50),
        field('tid', '授課教練', 'select', c.get('tid'), options=trainers),
        field('codate', '日期', 'date', c.get('codate')),
        field('starttime', '開始時間', 'time', c.get('starttime')),
        field('endtime', '結束時間', 'time', c.get('endtime')),
        field('location', '教室', value=c.get('location'), required=False, maxlength=50),
        field('capacity', '名額', 'number', c.get('capacity'), min=1),
    ]


@manager.route('/courses', methods=['GET', 'POST'])
@role_required('manager')
def courses():
    if request.method == 'POST' and request.form.get('action') == 'delete':
        cono = request.form.get('cono')
        run(lambda: Course.delete(cono), f'已刪除課程 {cono}（相關預約一併刪除）。')
        return redirect(url_for('manager.courses'))
    return render_template('admin_courses.html', courses=Course.list())


@manager.route('/courses/new', methods=['GET', 'POST'])
@role_required('manager')
def courses_new():
    if request.method == 'POST':
        data = form_data(COURSE_COLUMNS)
        try:
            cono = Course.create(data)
            flash(f'已新增課程 {cono}。', 'success')
            return redirect(url_for('manager.courses'))
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
    return render_form('新增課程', course_fields(), url_for('manager.courses'), submit='新增')


@manager.route('/courses/<cono>/edit', methods=['GET', 'POST'])
@role_required('manager')
def courses_edit(cono):
    c = Course.get(cono)
    if c is None:
        flash('找不到這堂課程。', 'warning')
        return redirect(url_for('manager.courses'))
    if request.method == 'POST':
        data = form_data(COURSE_COLUMNS)
        try:
            if Course.update(cono, data):
                flash(f'已更新課程 {cono}。', 'success')
                return redirect(url_for('manager.courses'))
            flash('名額不能少於目前的有效預約人數。', 'warning')
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
    return render_form(f'編輯課程 {cono}', course_fields(c), url_for('manager.courses'))


@manager.route('/courses/<cono>/roster', methods=['GET', 'POST'])
@role_required('manager')
def courses_roster(cono):
    c = Course.get(cono)
    if c is None:
        flash('找不到這堂課程。', 'warning')
        return redirect(url_for('manager.courses'))
    if request.method == 'POST':
        mid, status = request.form.get('mid'), request.form.get('status')
        if status in ('attended', 'absent'):
            run(lambda: Course.mark(cono, mid, status), f'已將 {mid} 標記為{"出席" if status == "attended" else "缺席"}。')
        return redirect(url_for('manager.courses_roster', cono=cono))
    return render_template('admin_roster.html', c=c, roster=Course.roster(cono))


# ================================================================ 方案
PLAN_COLUMNS = ['pname', 'duration', 'price']


def plan_fields(p=None):
    p = p or {}
    return [
        field('pname', '方案名稱', value=p.get('pname'), maxlength=50),
        field('duration', '天數', 'number', p.get('duration'), min=1),
        field('price', '價格', 'number', p.get('price'), min=0, step=1),
    ]


@manager.route('/plans', methods=['GET', 'POST'])
@role_required('manager')
def plans():
    if request.method == 'POST' and request.form.get('action') == 'delete':
        pid = request.form.get('pid')
        run(lambda: Plan.delete(pid), f'已刪除方案 {pid}。')
        return redirect(url_for('manager.plans'))
    return render_template('admin_plans.html', plans=Plan.list())


@manager.route('/plans/new', methods=['GET', 'POST'])
@role_required('manager')
def plans_new():
    if request.method == 'POST':
        try:
            pid = Plan.create(form_data(PLAN_COLUMNS))
            flash(f'已新增方案 {pid}。', 'success')
            return redirect(url_for('manager.plans'))
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
    return render_form('新增方案', plan_fields(), url_for('manager.plans'), submit='新增')


@manager.route('/plans/<pid>/edit', methods=['GET', 'POST'])
@role_required('manager')
def plans_edit(pid):
    p = Plan.get(pid)
    if p is None:
        flash('找不到這個方案。', 'warning')
        return redirect(url_for('manager.plans'))
    if request.method == 'POST':
        data = form_data(PLAN_COLUMNS)
        if run(lambda: Plan.update(pid, data), f'已更新方案 {pid}（已簽約的合約金額不受影響）。'):
            return redirect(url_for('manager.plans'))
    return render_form(f'編輯方案 {pid}', plan_fields(p), url_for('manager.plans'),
                       note='調整價格只影響之後的新合約，已簽約的金額不會改變。')


# ================================================================ 合約
@manager.route('/contracts')
@role_required('manager')
def contracts():
    return render_template('admin_contracts.html', contracts=Contract.list(), expiring=Contract.expiring(7))


@manager.route('/contracts/new', methods=['GET', 'POST'])
@role_required('manager')
def contracts_new():
    members_opt = [(m['mid'], f"{m['mid']} {m['mname']}") for m in Member.options()]
    plans_opt = [(p['pid'], f"{p['pname']}（{p['duration']} 天，{p['price']:,.0f} 元）") for p in Plan.options()]
    fields = [
        field('mid', '會員', 'select', request.args.get('mid'), options=members_opt),
        field('pid', '方案', 'select', options=plans_opt),
        field('startdate', '開始日期', 'date', date.today()),
        field('paymentmethod', '付款方式', 'select', options=PAYMENT_OPTIONS),
    ]
    if request.method == 'POST':
        data = form_data(['mid', 'pid', 'startdate', 'paymentmethod'])
        try:
            cno = Contract.create(data['mid'], data['pid'], data['startdate'], data['paymentmethod'])
            flash(f'已建立合約 {cno}，金額依方案目前價格計算。', 'success')
            return redirect(url_for('manager.contracts'))
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
    return render_form('新增合約', fields, url_for('manager.contracts'), submit='建立合約',
                       note='合約金額會自動帶入方案目前的價格，到期日依方案天數計算。')


# ================================================================ 退款審核
@manager.route('/refunds', methods=['GET', 'POST'])
@role_required('manager')
def refunds():
    if request.method == 'POST':
        cno, rno, status = request.form.get('cno'), request.form.get('rno'), request.form.get('status')
        if status in ('approved', 'rejected'):
            run(lambda: Refund.review(cno, rno, status),
                f'退款 {cno}-{rno} 已{"核准" if status == "approved" else "駁回"}。')
        return redirect(url_for('manager.refunds', status=request.args.get('status', '')))
    status = request.args.get('status') or None
    return render_template('admin_refunds.html', refunds=Refund.list(status=status), status=status)
