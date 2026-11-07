"""所有資料庫存取都集中在這個檔案（對應 db/03_feature_queries.sql 的 Q01～Q15、W01～W11）。

連線時已把 search_path 設成 gym schema，所以 SQL 裡直接寫表格名稱即可。
所有使用者輸入都用 %s 參數綁定，避免 SQL injection。
"""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SCHEMA = os.getenv('DB_SCHEMA', 'gym')


class DB:
    _pool = None

    @classmethod
    def _get_pool(cls):
        if cls._pool is None:
            cls._pool = pool.SimpleConnectionPool(
                1, 10,
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT'),
                dbname=os.getenv('DB_NAME'),
                options=f'-c search_path={SCHEMA},public -c TimeZone=Asia/Taipei',
            )
        return cls._pool

    @classmethod
    @contextmanager
    def transaction(cls):
        """一個交易：區塊內全部成功才 COMMIT，任何錯誤就 ROLLBACK。"""
        connection = cls._get_pool().getconn()
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cls._get_pool().putconn(connection)

    @classmethod
    def fetchall(cls, sql, params=None):
        with cls.transaction() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @classmethod
    def fetchone(cls, sql, params=None):
        with cls.transaction() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    @classmethod
    def execute(cls, sql, params=None):
        """執行新增／修改／刪除，回傳影響的筆數。"""
        with cls.transaction() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def friendly_error(e):
    """把資料庫錯誤轉成給使用者看的中文訊息。"""
    code = getattr(e, 'pgcode', None)
    if code == '23503':
        return '這筆資料仍被其他資料使用（例如已有合約、課程或預約），無法刪除或修改。'
    if code == '23505':
        return '資料重複：編號、帳號、email 或電話已經存在。'
    if code == '23514':
        return '資料不符合規則（例如時間、日期或金額不合理），請檢查後再送出。'
    if code == '23502':
        return '有必填欄位沒有填寫。'
    if code == 'P0001':  # 觸發器 RAISE EXCEPTION 的訊息，例如課程額滿
        return e.diag.message_primary
    if code and code.startswith('22'):
        return '輸入的資料格式不正確。'
    return '資料庫發生錯誤，請稍後再試。'


def next_id(table, column, prefix, width=3):
    """產生下一個編號，例如 M008 → M009。只看「前綴＋數字」格式的編號。"""
    sql = f'''
        SELECT coalesce(max(substring({column} FROM %s)::int), 0) + 1 AS n
        FROM {table} WHERE {column} ~ %s
    '''
    n = DB.fetchone(sql, (f'^{prefix}([0-9]+)$', f'^{prefix}[0-9]+$'))['n']
    return f'{prefix}{n:0{width}d}'


# ---------------------------------------------------------------- 帳號
class Account:
    @staticmethod
    def get(account):
        sql = '''
            SELECT a.account, a.password, a.identity, a.mId AS mid,
                   coalesce(m.mName, '管理者') AS name
            FROM account a LEFT JOIN member m ON m.mId = a.mId
            WHERE a.account = %s
        '''
        return DB.fetchone(sql, (account,))

    @staticmethod
    def exists(account):
        return DB.fetchone('SELECT 1 FROM account WHERE account = %s', (account,)) is not None

    @staticmethod
    def of_member(mid):
        return DB.fetchone('SELECT account FROM account WHERE mId = %s', (mid,))


# ---------------------------------------------------------------- 會員
class Member:
    # Q01 會員清單與多支電話；Q02 關鍵字搜尋姓名、email、電話
    @staticmethod
    def list(keyword=None):
        sql = '''
            SELECT m.mId AS mid, m.mName AS mname, m.email, m.sex, m.birthday,
                   coalesce(ph.phones, '') AS phones, a.account,
                   (SELECT count(*) FROM contract c WHERE c.mId = m.mId) AS contract_count
            FROM member m
            LEFT JOIN (
                SELECT mId, string_agg(mPhone, ', ' ORDER BY mPhone) AS phones
                FROM memphone GROUP BY mId
            ) ph ON ph.mId = m.mId
            LEFT JOIN account a ON a.mId = m.mId
        '''
        params = None
        if keyword:
            sql += '''
            WHERE m.mName ILIKE %s OR m.email ILIKE %s OR m.mId ILIKE %s
               OR EXISTS (SELECT 1 FROM memphone p WHERE p.mId = m.mId AND p.mPhone ILIKE %s)
            '''
            like = f'%{keyword}%'
            params = (like, like, like, like)
        sql += ' ORDER BY m.mId'
        return DB.fetchall(sql, params)

    @staticmethod
    def get(mid):
        sql = '''SELECT mId AS mid, mName AS mname, email, sex, birthday
                 FROM member WHERE mId = %s'''
        return DB.fetchone(sql, (mid,))

    @staticmethod
    def phones(mid):
        sql = 'SELECT mPhone AS mphone FROM memphone WHERE mId = %s ORDER BY mPhone'
        return [r['mphone'] for r in DB.fetchall(sql, (mid,))]

    @staticmethod
    def options():
        return DB.fetchall('SELECT mId AS mid, mName AS mname FROM member ORDER BY mId')

    # W01 新增會員（同時新增電話與登入帳號，同一個交易）
    @staticmethod
    def create(data, phone=None, account=None, password_hash=None):
        mid = next_id('member', 'mId', 'M')
        with DB.transaction() as cur:
            cur.execute('''INSERT INTO member (mId, mName, email, sex, birthday)
                           VALUES (%s, %s, %s, %s, %s)''',
                        (mid, data['mname'], data['email'], data['sex'], data['birthday']))
            if phone:
                cur.execute('INSERT INTO memphone (mPhone, mId) VALUES (%s, %s)', (phone, mid))
            if account:
                cur.execute('''INSERT INTO account (account, password, identity, mId)
                               VALUES (%s, %s, 'member', %s)''', (account, password_hash, mid))
        return mid

    # W01 更新會員資料
    @staticmethod
    def update(mid, data):
        sql = '''UPDATE member SET mName = %s, email = %s, sex = %s, birthday = %s
                 WHERE mId = %s'''
        return DB.execute(sql, (data['mname'], data['email'], data['sex'], data['birthday'], mid))

    # W11 刪除會員：有合約者受 RESTRICT 保護；電話、帳號、預約、指派會連動刪除
    @staticmethod
    def delete(mid):
        return DB.execute('DELETE FROM member WHERE mId = %s', (mid,))

    # W01 增刪聯絡電話
    @staticmethod
    def add_phone(mid, phone):
        return DB.execute('INSERT INTO memphone (mPhone, mId) VALUES (%s, %s)', (phone, mid))

    @staticmethod
    def delete_phone(mid, phone):
        return DB.execute('DELETE FROM memphone WHERE mId = %s AND mPhone = %s', (mid, phone))


# ---------------------------------------------------------------- 教練
class Trainer:
    # Q03 教練、直屬主管、負責會員數、授課數
    @staticmethod
    def list():
        sql = '''
            SELECT t.tId AS tid, t.tName AS tname, t.tPhone AS tphone, t.speciality,
                   t.history, t.leader, l.tName AS leader_name,
                   (SELECT count(*) FROM assignedto a WHERE a.tId = t.tId) AS member_count,
                   (SELECT count(*) FROM course c WHERE c.tId = t.tId) AS course_count
            FROM trainer t LEFT JOIN trainer l ON l.tId = t.leader
            ORDER BY t.tId
        '''
        return DB.fetchall(sql)

    @staticmethod
    def get(tid):
        sql = '''SELECT tId AS tid, tName AS tname, tPhone AS tphone, speciality, history, leader
                 FROM trainer WHERE tId = %s'''
        return DB.fetchone(sql, (tid,))

    @staticmethod
    def options():
        return DB.fetchall('SELECT tId AS tid, tName AS tname FROM trainer ORDER BY tId')

    # W02 新增教練、指定主管
    @staticmethod
    def create(data):
        tid = next_id('trainer', 'tId', 'T')
        DB.execute('''INSERT INTO trainer (tId, tName, tPhone, speciality, history, leader)
                      VALUES (%s, %s, %s, %s, %s, %s)''',
                   (tid, data['tname'], data['tphone'], data['speciality'],
                    data['history'], data['leader'] or None))
        return tid

    @staticmethod
    def update(tid, data):
        sql = '''UPDATE trainer SET tName = %s, tPhone = %s, speciality = %s,
                        history = %s, leader = %s
                 WHERE tId = %s'''
        return DB.execute(sql, (data['tname'], data['tphone'], data['speciality'],
                                data['history'], data['leader'] or None, tid))

    @staticmethod
    def delete(tid):
        return DB.execute('DELETE FROM trainer WHERE tId = %s', (tid,))

    # Q04 指定教練的服務會員
    @staticmethod
    def members(tid):
        sql = '''
            SELECT m.mId AS mid, m.mName AS mname, m.email
            FROM assignedto a JOIN member m ON m.mId = a.mId
            WHERE a.tId = %s ORDER BY m.mId
        '''
        return DB.fetchall(sql, (tid,))

    # W02 分派／解除會員與教練關係
    @staticmethod
    def assign(tid, mid):
        sql = '''INSERT INTO assignedto (mId, tId) VALUES (%s, %s)
                 ON CONFLICT (mId, tId) DO NOTHING'''
        return DB.execute(sql, (mid, tid))

    @staticmethod
    def unassign(tid, mid):
        return DB.execute('DELETE FROM assignedto WHERE mId = %s AND tId = %s', (mid, tid))

    @staticmethod
    def of_member(mid):
        sql = '''SELECT t.tName AS tname, t.speciality, t.tPhone AS tphone
                 FROM assignedto a JOIN trainer t ON t.tId = a.tId
                 WHERE a.mId = %s ORDER BY t.tId'''
        return DB.fetchall(sql, (mid,))


# ---------------------------------------------------------------- 課程
COURSE_START = "((c.coDate + c.startTime) AT TIME ZONE 'Asia/Taipei')"
COURSE_END = "((c.coDate + c.endTime) AT TIME ZONE 'Asia/Taipei')"


class Course:
    # Q05 課表、有效佔位、剩餘名額與滿班狀態（upcoming_only=True 只列未開始的課程）
    @staticmethod
    def list(upcoming_only=False, keyword=None, mid=None):
        sql = f'''
            SELECT c.coNo AS cono, c.coName AS coname, c.capacity, c.location,
                   c.coDate AS codate, c.startTime AS starttime, c.endTime AS endtime,
                   c.tId AS tid, t.tName AS tname,
                   count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS occupied,
                   c.capacity - count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS available,
                   {COURSE_START} > CURRENT_TIMESTAMP AS upcoming,
                   {COURSE_END} <= CURRENT_TIMESTAMP AS ended,
                   bool_or(b.mId = %s AND b.bStatus = 'booked') AS booked_by_me
            FROM course c JOIN trainer t ON t.tId = c.tId
            LEFT JOIN booking b ON b.coNo = c.coNo
            WHERE TRUE
        '''
        params = [mid]
        if upcoming_only:
            sql += f' AND {COURSE_START} > CURRENT_TIMESTAMP'
        if keyword:
            sql += ' AND (c.coName ILIKE %s OR t.tName ILIKE %s OR c.location ILIKE %s)'
            params += [f'%{keyword}%'] * 3
        sql += ' GROUP BY c.coNo, t.tName ORDER BY c.coDate, c.startTime, c.coNo'
        return DB.fetchall(sql, params)

    @staticmethod
    def get(cono):
        sql = f'''SELECT c.coNo AS cono, c.coName AS coname, c.capacity, c.location,
                         c.coDate AS codate, c.startTime AS starttime, c.endTime AS endtime,
                         c.tId AS tid, t.tName AS tname,
                         {COURSE_START} > CURRENT_TIMESTAMP AS upcoming,
                         {COURSE_END} <= CURRENT_TIMESTAMP AS ended
                  FROM course c JOIN trainer t ON t.tId = c.tId WHERE c.coNo = %s'''
        return DB.fetchone(sql, (cono,))

    # W05 建立／修改課程
    @staticmethod
    def create(data):
        cono = next_id('course', 'coNo', 'CO')
        DB.execute('''INSERT INTO course (coNo, coName, capacity, location, coDate, startTime, endTime, tId)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                   (cono, data['coname'], data['capacity'], data['location'], data['codate'],
                    data['starttime'], data['endtime'], data['tid']))
        return cono

    @staticmethod
    def update(cono, data):
        # 名額不能改得比目前有效預約人數還少
        sql = '''UPDATE course SET coName = %s, capacity = %s, location = %s, coDate = %s,
                        startTime = %s, endTime = %s, tId = %s
                 WHERE coNo = %s
                   AND %s >= (SELECT count(*) FROM booking b
                              WHERE b.coNo = %s AND b.bStatus <> 'cancelled')'''
        return DB.execute(sql, (data['coname'], data['capacity'], data['location'], data['codate'],
                                data['starttime'], data['endtime'], data['tid'], cono,
                                data['capacity'], cono))

    @staticmethod
    def delete(cono):
        return DB.execute('DELETE FROM course WHERE coNo = %s', (cono,))

    # Q07 課程點名表
    @staticmethod
    def roster(cono):
        sql = '''SELECT m.mId AS mid, m.mName AS mname, b.bStatus AS bstatus, b.bookingTime AS bookingtime
                 FROM booking b JOIN member m ON m.mId = b.mId
                 WHERE b.coNo = %s ORDER BY (b.bStatus = 'cancelled'), m.mId'''
        return DB.fetchall(sql, (cono,))

    # W08 點名（只對已結束的課程）
    @staticmethod
    def mark(cono, mid, status):
        sql = f'''
            UPDATE booking b SET bStatus = %s
            FROM course c
            WHERE c.coNo = b.coNo AND b.coNo = %s AND b.mId = %s
              AND b.bStatus IN ('booked', 'attended', 'absent')
              AND {COURSE_END} <= CURRENT_TIMESTAMP
        '''
        return DB.execute(sql, (status, cono, mid))


# ---------------------------------------------------------------- 預約
class Booking:
    # Q06 會員預約歷史與狀態
    @staticmethod
    def of_member(mid):
        sql = f'''
            SELECT c.coNo AS cono, c.coName AS coname, c.coDate AS codate,
                   c.startTime AS starttime, c.endTime AS endtime, c.location,
                   t.tName AS tname, b.bStatus AS bstatus, b.bookingTime AS bookingtime,
                   {COURSE_START} > CURRENT_TIMESTAMP AS upcoming
            FROM booking b JOIN course c ON c.coNo = b.coNo
            JOIN trainer t ON t.tId = c.tId
            WHERE b.mId = %s
            ORDER BY c.coDate DESC, c.startTime DESC
        '''
        return DB.fetchall(sql, (mid,))

    @staticmethod
    def has_valid_contract(mid, cono):
        """預約規則：課程日期要落在會員某張合約的有效期間內。"""
        sql = '''SELECT 1 FROM contract ct JOIN course c ON c.coNo = %s
                 WHERE ct.mId = %s AND c.coDate BETWEEN ct.startDate AND ct.endDate'''
        return DB.fetchone(sql, (cono, mid)) is not None

    # W06 預約＋W07 重新預約：課程未開始才能預約；曾取消過就把原本那筆改回 booked
    # 名額由資料庫觸發器 trg_booking_capacity 檢查，額滿會丟出錯誤
    @staticmethod
    def book(mid, cono):
        sql = f'''
            INSERT INTO booking AS b (coNo, mId, bStatus, bookingTime)
            SELECT c.coNo, %s, 'booked', CURRENT_TIMESTAMP FROM course c
            WHERE c.coNo = %s AND {COURSE_START} > CURRENT_TIMESTAMP
            ON CONFLICT (coNo, mId) DO UPDATE
                SET bStatus = 'booked', bookingTime = CURRENT_TIMESTAMP
                WHERE b.bStatus = 'cancelled'
            RETURNING b.coNo
        '''
        with DB.transaction() as cur:
            cur.execute(sql, (mid, cono))
            return cur.fetchone() is not None

    # W07 取消預約（課程開始前才能取消）
    @staticmethod
    def cancel(mid, cono):
        sql = f'''
            UPDATE booking b SET bStatus = 'cancelled'
            FROM course c
            WHERE c.coNo = b.coNo AND b.coNo = %s AND b.mId = %s
              AND b.bStatus = 'booked' AND {COURSE_START} > CURRENT_TIMESTAMP
        '''
        return DB.execute(sql, (cono, mid))


# ---------------------------------------------------------------- 方案
class Plan:
    # Q08 方案、合約銷售與核准退款後淨收款
    @staticmethod
    def list():
        sql = '''
            WITH refunds AS (
                SELECT cNo, sum(rAmount) FILTER (WHERE status = 'approved') AS approved_amount
                FROM refund GROUP BY cNo
            )
            SELECT p.pId AS pid, p.pName AS pname, p.duration, p.price,
                   count(c.cNo) AS contract_count,
                   coalesce(sum(c.cAmount), 0) AS gross_amount,
                   coalesce(sum(r.approved_amount), 0) AS approved_refunds,
                   coalesce(sum(c.cAmount - coalesce(r.approved_amount, 0)), 0) AS net_collected
            FROM plan p LEFT JOIN contract c ON c.pId = p.pId
            LEFT JOIN refunds r ON r.cNo = c.cNo
            GROUP BY p.pId ORDER BY p.pId
        '''
        return DB.fetchall(sql)

    @staticmethod
    def get(pid):
        return DB.fetchone('SELECT pId AS pid, pName AS pname, duration, price FROM plan WHERE pId = %s', (pid,))

    @staticmethod
    def options():
        return DB.fetchall('SELECT pId AS pid, pName AS pname, duration, price FROM plan ORDER BY price')

    # W03 新增／調整方案（價格調整不影響已簽約的 cAmount）
    @staticmethod
    def create(data):
        pid = next_id('plan', 'pId', 'P')
        DB.execute('INSERT INTO plan (pId, pName, duration, price) VALUES (%s, %s, %s, %s)',
                   (pid, data['pname'], data['duration'], data['price']))
        return pid

    @staticmethod
    def update(pid, data):
        return DB.execute('UPDATE plan SET pName = %s, duration = %s, price = %s WHERE pId = %s',
                          (data['pname'], data['duration'], data['price'], pid))

    @staticmethod
    def delete(pid):
        return DB.execute('DELETE FROM plan WHERE pId = %s', (pid,))


# ---------------------------------------------------------------- 合約
CONTRACT_SELECT = '''
    WITH refunds AS (
        SELECT cNo,
               sum(rAmount) FILTER (WHERE status = 'approved') AS approved_amount,
               sum(rAmount) FILTER (WHERE status IN ('pending', 'approved')) AS reserved_amount
        FROM refund GROUP BY cNo
    )
    SELECT c.cNo AS cno, c.cDate AS cdate, c.startDate AS startdate, c.endDate AS enddate,
           c.cAmount AS camount, c.paymentMethod AS paymentmethod,
           c.mId AS mid, m.mName AS mname, c.pId AS pid, p.pName AS pname,
           coalesce(r.approved_amount, 0) AS approved_refunds,
           c.cAmount - coalesce(r.reserved_amount, 0) AS refundable_balance,
           CASE WHEN c.cAmount > 0 AND coalesce(r.approved_amount, 0) >= c.cAmount THEN 'fully_refunded'
                WHEN c.startDate > CURRENT_DATE THEN 'not_started'
                WHEN c.endDate < CURRENT_DATE THEN 'expired'
                ELSE 'active' END AS derived_status
    FROM contract c JOIN member m ON m.mId = c.mId
    JOIN plan p ON p.pId = c.pId
    LEFT JOIN refunds r ON r.cNo = c.cNo
'''


class Contract:
    # Q09 合約狀態（由日期推導）＋ Q12 可退款餘額
    @staticmethod
    def list(mid=None):
        if mid:
            return DB.fetchall(CONTRACT_SELECT + ' WHERE c.mId = %s ORDER BY c.cDate DESC, c.cNo DESC', (mid,))
        return DB.fetchall(CONTRACT_SELECT + ' ORDER BY c.cNo')

    @staticmethod
    def get(cno):
        return DB.fetchone(CONTRACT_SELECT + ' WHERE c.cNo = %s', (cno,))

    # Q10 未來 7 天內到期的合約
    @staticmethod
    def expiring(days=7):
        sql = '''
            SELECT c.cNo AS cno, m.mId AS mid, m.mName AS mname, c.endDate AS enddate,
                   c.endDate - CURRENT_DATE AS days_left
            FROM contract c JOIN member m ON m.mId = c.mId
            WHERE c.startDate <= CURRENT_DATE
              AND c.endDate BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
            ORDER BY c.endDate, c.cNo
        '''
        return DB.fetchall(sql, (days,))

    # W04 簽約：存入當時的方案價格，到期日 = 開始日 + 天數 - 1
    @staticmethod
    def create(mid, pid, start_date, payment_method):
        cno = next_id('contract', 'cNo', 'C')
        sql = '''
            INSERT INTO contract (cNo, cDate, startDate, endDate, cAmount, paymentMethod, pId, mId)
            SELECT %s, CURRENT_DATE, %s::date, %s::date + p.duration - 1, p.price, %s, p.pId, %s
            FROM plan p WHERE p.pId = %s
        '''
        DB.execute(sql, (cno, start_date, start_date, payment_method, mid, pid))
        return cno


# ---------------------------------------------------------------- 退款
class Refund:
    # Q11 退款申請明細
    @staticmethod
    def list(mid=None, status=None):
        sql = '''
            SELECT r.rNo AS rno, r.cNo AS cno, r.rAmount AS ramount, r.rDate AS rdate,
                   r.status, r.reason, m.mId AS mid, m.mName AS mname,
                   p.pName AS pname, c.cAmount AS camount
            FROM refund r JOIN contract c ON c.cNo = r.cNo
            JOIN member m ON m.mId = c.mId JOIN plan p ON p.pId = c.pId
            WHERE TRUE
        '''
        params = []
        if mid:
            sql += ' AND c.mId = %s'
            params.append(mid)
        if status:
            sql += ' AND r.status = %s'
            params.append(status)
        sql += " ORDER BY (r.status <> 'pending'), r.rDate DESC, r.cNo, r.rNo"
        return DB.fetchall(sql, params)

    # W09 申請退款：先鎖合約，再取 MAX+1 當序號；同時檢查可退餘額（Q12）
    @staticmethod
    def apply(mid, cno, amount, reason):
        with DB.transaction() as cur:
            cur.execute('SELECT cAmount FROM contract WHERE cNo = %s AND mId = %s FOR UPDATE', (cno, mid))
            contract = cur.fetchone()
            if contract is None:
                return '找不到這張合約。'
            cur.execute('''SELECT %s - coalesce(sum(rAmount), 0) AS balance FROM refund
                           WHERE cNo = %s AND status IN ('pending', 'approved')''',
                        (contract['camount'], cno))
            balance = cur.fetchone()['balance']
            if amount > balance:
                return f'退款金額超過可退餘額（最多 {balance:,.0f} 元）。'
            cur.execute('''
                INSERT INTO refund (rNo, cNo, rAmount, rDate, status, reason)
                SELECT coalesce(max(rNo), 0) + 1, %s, %s, CURRENT_DATE, 'pending', %s
                FROM refund WHERE cNo = %s
            ''', (cno, amount, reason, cno))
        return None

    # W10 審核退款：只處理待審案件
    @staticmethod
    def review(cno, rno, status):
        sql = "UPDATE refund SET status = %s WHERE cNo = %s AND rNo = %s AND status = 'pending'"
        return DB.execute(sql, (status, cno, rno))


# ---------------------------------------------------------------- 統計
class Analysis:
    # Q15 系統總覽
    @staticmethod
    def overview():
        sql = f'''
            SELECT (SELECT count(*) FROM member) AS members,
                   (SELECT count(*) FROM trainer) AS trainers,
                   (SELECT count(*) FROM course) AS courses,
                   (SELECT count(*) FROM booking b JOIN course c ON c.coNo = b.coNo
                    WHERE b.bStatus = 'booked' AND {COURSE_START} > CURRENT_TIMESTAMP) AS upcoming_reservations,
                   (SELECT coalesce(sum(cAmount), 0) FROM contract) AS gross_collected,
                   (SELECT coalesce(sum(rAmount), 0) FROM refund WHERE status = 'approved') AS approved_refunds,
                   (SELECT count(*) FROM refund WHERE status = 'pending') AS pending_refunds
        '''
        return DB.fetchone(sql)

    # Q13 每月收款與核准退款
    @staticmethod
    def monthly_cash_flow():
        sql = '''
            WITH flows AS (
                SELECT date_trunc('month', cDate::timestamp)::date AS month,
                       cAmount AS collected, 0::numeric AS refunded FROM contract
                UNION ALL
                SELECT date_trunc('month', rDate::timestamp)::date, 0::numeric, rAmount
                FROM refund WHERE status = 'approved'
            )
            SELECT to_char(month, 'YYYY-MM') AS month,
                   sum(collected) AS collected, sum(refunded) AS refunded,
                   sum(collected) - sum(refunded) AS net_cash_flow
            FROM flows GROUP BY month ORDER BY month
        '''
        return DB.fetchall(sql)

    # Q14 課程熱門程度與出席率
    @staticmethod
    def course_popularity():
        sql = '''
            SELECT c.coNo AS cono, c.coName AS coname, c.capacity,
                   count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS occupied,
                   round(100.0 * count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') / c.capacity, 1) AS occupancy_pct,
                   count(b.mId) FILTER (WHERE b.bStatus = 'attended') AS attended,
                   round(100.0 * count(b.mId) FILTER (WHERE b.bStatus = 'attended')
                         / nullif(count(b.mId) FILTER (WHERE b.bStatus IN ('attended', 'absent')), 0), 1)
                       AS attendance_pct
            FROM course c LEFT JOIN booking b ON b.coNo = c.coNo
            GROUP BY c.coNo ORDER BY occupied DESC, c.coNo
        '''
        return DB.fetchall(sql)
