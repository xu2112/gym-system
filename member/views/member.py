"""會員前台：預約課程、我的預約、合約與退款、個人資料。"""
from datetime import date

import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user

from api.api import role_required
from api.forms import PAYMENT_OPTIONS, to_decimal
from api.sql import Member, Trainer, Course, Booking, Plan, Contract, Refund, friendly_error

member = Blueprint('member', __name__, template_folder='../templates')


@member.route('/')
@role_required('member')
def home():
    return redirect(url_for('member.courses'))


@member.route('/courses', methods=['GET', 'POST'])
@role_required('member')
def courses():
    mid = current_user.mid
    if request.method == 'POST':
        cono = request.form.get('cono')
        course = Course.get(cono)
        if course is None or not course['upcoming']:
            flash('這堂課已經開始或不存在，無法預約。', 'warning')
        elif not Booking.has_valid_contract(mid, cono):
            flash('課程日期不在您的合約有效期間內，請先到「合約與退款」購買方案。', 'warning')
        else:
            try:
                if Booking.book(mid, cono):
                    flash(f'預約成功：{course["coname"]}（{course["codate"]} {course["starttime"]:%H:%M}）', 'success')
                else:
                    flash('您已經預約過這堂課了。', 'info')
            except psycopg2.Error as e:
                flash(friendly_error(e), 'danger')
        return redirect(url_for('member.courses', keyword=request.args.get('keyword', '')))

    keyword = request.args.get('keyword', '').strip()
    rows = Course.list(upcoming_only=True, keyword=keyword or None, mid=mid)
    return render_template('member_courses.html', courses=rows, keyword=keyword)


@member.route('/bookings', methods=['GET', 'POST'])
@role_required('member')
def bookings():
    mid = current_user.mid
    if request.method == 'POST':
        cono = request.form.get('cono')
        if Booking.cancel(mid, cono):
            flash('已取消預約。', 'success')
        else:
            flash('只能取消尚未開始的課程預約。', 'warning')
        return redirect(url_for('member.bookings'))
    return render_template('member_bookings.html', bookings=Booking.of_member(mid))


@member.route('/contracts', methods=['GET', 'POST'])
@role_required('member')
def contracts():
    mid = current_user.mid
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'buy':
                start = request.form.get('startdate') or date.today().isoformat()
                if start < date.today().isoformat():
                    flash('開始日期不能早於今天。', 'warning')
                elif Plan.get(request.form.get('pid')) is None:
                    flash('請選擇方案。', 'warning')
                else:
                    cno = Contract.create(mid, request.form['pid'], start, request.form.get('paymentmethod'))
                    flash(f'購買成功，合約編號 {cno}。', 'success')
            elif action == 'refund':
                amount = to_decimal(request.form.get('ramount'))
                reason = request.form.get('reason', '').strip()
                if amount is None or amount <= 0:
                    flash('請輸入正確的退款金額。', 'warning')
                elif not reason:
                    flash('請填寫退款原因。', 'warning')
                else:
                    error = Refund.apply(mid, request.form.get('cno'), amount, reason)
                    flash(error or '已送出退款申請，等待管理者審核。', 'warning' if error else 'success')
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
        return redirect(url_for('member.contracts'))

    return render_template('member_contracts.html',
                           contracts=Contract.list(mid),
                           refunds=Refund.list(mid=mid),
                           plans=Plan.options(),
                           payment_options=PAYMENT_OPTIONS,
                           today=date.today().isoformat())


@member.route('/profile', methods=['GET', 'POST'])
@role_required('member')
def profile():
    mid = current_user.mid
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'update':
                data = {k: request.form.get(k, '').strip() or None for k in ('mname', 'email', 'sex', 'birthday')}
                Member.update(mid, data)
                flash('個人資料已更新。', 'success')
            elif action == 'add_phone':
                phone = request.form.get('phone', '').strip()
                if phone:
                    Member.add_phone(mid, phone)
                    flash('已新增電話。', 'success')
            elif action == 'delete_phone':
                Member.delete_phone(mid, request.form.get('phone'))
                flash('已刪除電話。', 'success')
        except psycopg2.Error as e:
            flash(friendly_error(e), 'danger')
        return redirect(url_for('member.profile'))

    return render_template('member_profile.html',
                           me=Member.get(mid),
                           phones=Member.phones(mid),
                           trainers=Trainer.of_member(mid))
