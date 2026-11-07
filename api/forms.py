"""共用表單：新增／編輯頁面都用 templates/form.html，只要給欄位清單就能產生表單。"""
from datetime import date, time
from decimal import Decimal, InvalidOperation

SEX_OPTIONS = [('F', '女'), ('M', '男')]
PAYMENT_OPTIONS = [('credit_card', '信用卡'), ('bank_transfer', '銀行轉帳'), ('cash', '現金')]

LABELS = {
    # 預約狀態
    'booked': '已預約', 'cancelled': '已取消', 'attended': '已出席', 'absent': '缺席',
    # 退款狀態
    'pending': '審核中', 'approved': '已核准', 'rejected': '已駁回',
    # 合約狀態
    'active': '有效', 'expired': '已到期', 'not_started': '未開始', 'fully_refunded': '已全額退款',
    # 付款方式
    'credit_card': '信用卡', 'bank_transfer': '銀行轉帳', 'cash': '現金',
    # 性別
    'F': '女', 'M': '男',
}

BADGES = {
    'booked': 'primary', 'cancelled': 'secondary', 'attended': 'success', 'absent': 'danger',
    'pending': 'warning', 'approved': 'success', 'rejected': 'secondary',
    'active': 'success', 'expired': 'secondary', 'not_started': 'info', 'fully_refunded': 'dark',
}


def field(name, label, type='text', value=None, required=True, options=None, **attrs):
    """一個表單欄位。type 可以是 text、email、number、date、time、textarea、select。"""
    if isinstance(value, (date, time)):
        value = value.strftime('%H:%M') if isinstance(value, time) else value.isoformat()
    if isinstance(value, Decimal):
        value = format(value.normalize(), 'f')
    return {'name': name, 'label': label, 'type': type, 'value': '' if value is None else value,
            'required': required, 'options': options or [], 'attrs': attrs}


def fill(fields, form):
    """送出失敗時，把使用者剛剛輸入的內容放回表單。"""
    for f in fields:
        if f['name'] in form:
            f['value'] = form[f['name']]
    return fields


def to_decimal(text):
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None
