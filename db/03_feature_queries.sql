-- 整份可直接執行；所有新增／修改／刪除範例最後 ROLLBACK，不改變展示資料。
-- 實際使用請只選取需要的區塊，使用應用程式參數綁定，成功後自行 COMMIT。
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET LOCAL TIME ZONE 'Asia/Taipei';

-- Q01 會員清單與多支電話：先聚合電話，不讓後續 JOIN 造成列數倍增。
SELECT m.*, coalesce(ph.phones, '') AS phones
FROM gym.Member m
LEFT JOIN (
    SELECT mId, string_agg(mPhone, ', ' ORDER BY mPhone) AS phones
    FROM gym.MemPhone GROUP BY mId
) ph USING (mId)
ORDER BY m.mId;

-- Q02 搜尋會員。修改 CTE 裡的文字即能重用；可搜尋姓名、email、電話。
WITH params AS (SELECT '雅婷'::text AS keyword)
SELECT m.* FROM gym.Member m CROSS JOIN params p
WHERE m.mName ILIKE '%' || p.keyword || '%'
   OR m.email ILIKE '%' || p.keyword || '%'
   OR EXISTS (SELECT 1 FROM gym.MemPhone ph WHERE ph.mId = m.mId
              AND ph.mPhone ILIKE '%' || p.keyword || '%')
ORDER BY m.mId;

-- Q03 教練、直屬主管、負責會員數、授課數：各自計數，避免 M:N JOIN 重複計算。
SELECT t.tId, t.tName, t.speciality, l.tName AS leader_name,
       (SELECT count(*) FROM gym.AssignedTo a WHERE a.tId = t.tId) AS member_count,
       (SELECT count(*) FROM gym.Course c WHERE c.tId = t.tId) AS course_count
FROM gym.Trainer t LEFT JOIN gym.Trainer l ON l.tId = t.leader
ORDER BY t.tId;

-- Q04 指定教練的服務會員。
WITH params AS (SELECT 'T001'::varchar AS trainer_id)
SELECT t.tName, m.mId, m.mName
FROM gym.AssignedTo a JOIN gym.Member m USING (mId)
JOIN gym.Trainer t USING (tId) JOIN params p ON p.trainer_id = a.tId
ORDER BY m.mId;

-- Q05 未來課表、有效佔位、剩餘名額與滿班狀態。
SELECT c.*, t.tName, count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS occupied,
       c.capacity - count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS available,
       count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') >= c.capacity AS is_full
FROM gym.Course c JOIN gym.Trainer t USING (tId)
LEFT JOIN gym.Booking b USING (coNo)
WHERE ((c.coDate + c.startTime) AT TIME ZONE 'Asia/Taipei') > CURRENT_TIMESTAMP
GROUP BY c.coNo, t.tName
ORDER BY c.coDate, c.startTime, c.coNo;

-- Q06 會員預約歷史與狀態。
WITH params AS (SELECT 'M001'::varchar AS member_id)
SELECT b.mId, c.coNo, c.coName, c.coDate, c.startTime, c.endTime,
       c.location, t.tName, b.bStatus, b.bookingTime
FROM gym.Booking b JOIN gym.Course c USING (coNo)
JOIN gym.Trainer t USING (tId) JOIN params p ON p.member_id = b.mId
ORDER BY c.coDate, c.startTime;

-- Q07 課程點名表。
WITH params AS (SELECT 'CO007'::varchar AS course_no)
SELECT b.coNo, m.mId, m.mName, b.bStatus
FROM gym.Booking b JOIN gym.Member m USING (mId)
JOIN params p ON p.course_no = b.coNo
WHERE b.bStatus <> 'cancelled' ORDER BY m.mId;

-- Q08 方案、合約銷售與核准退款後淨收款。先按合約彙總退款，避免金額倍增。
WITH refunds AS (
    SELECT cNo, sum(rAmount) FILTER (WHERE status = 'approved') AS approved_amount
    FROM gym.Refund GROUP BY cNo
)
SELECT p.*, count(c.cNo) AS contract_count, coalesce(sum(c.cAmount), 0) AS gross_amount,
       coalesce(sum(r.approved_amount), 0) AS approved_refunds,
       coalesce(sum(c.cAmount - coalesce(r.approved_amount, 0)), 0) AS net_collected
FROM gym.Plan p LEFT JOIN gym.Contract c USING (pId)
LEFT JOIN refunds r USING (cNo)
GROUP BY p.pId ORDER BY p.pId;

-- Q09 合約有效狀態由日期推導，退款全額核准另列；不新增 status 欄位。
WITH refunds AS (
    SELECT cNo, sum(rAmount) FILTER (WHERE status = 'approved') AS approved_amount
    FROM gym.Refund GROUP BY cNo
)
SELECT c.*, m.mName, p.pName, coalesce(r.approved_amount, 0) AS approved_refunds,
       CASE WHEN c.cAmount > 0 AND coalesce(r.approved_amount, 0) >= c.cAmount THEN 'fully_refunded'
            WHEN c.startDate > CURRENT_DATE THEN 'not_started'
            WHEN c.endDate < CURRENT_DATE THEN 'expired' ELSE 'active' END AS derived_status
FROM gym.Contract c JOIN gym.Member m USING (mId)
JOIN gym.Plan p USING (pId) LEFT JOIN refunds r USING (cNo)
ORDER BY c.cNo;

-- Q10 未來 7 天內到期的合約，起訖皆含當日。
SELECT c.cNo, m.mId, m.mName, c.endDate, c.endDate - CURRENT_DATE AS days_left
FROM gym.Contract c JOIN gym.Member m USING (mId)
WHERE c.startDate <= CURRENT_DATE AND c.endDate BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
ORDER BY c.endDate, c.cNo;

-- Q11 退款申請明細，含會員、方案、原合約金額。
SELECT r.*, m.mId, m.mName, p.pName, c.cAmount
FROM gym.Refund r JOIN gym.Contract c USING (cNo)
JOIN gym.Member m USING (mId) JOIN gym.Plan p USING (pId)
ORDER BY r.rDate, r.cNo, r.rNo;

-- Q12 每張合約可再申請退款的金額（待審、核准皆保留額度；駁回釋出）。
SELECT c.cNo, c.cAmount,
       coalesce(sum(r.rAmount) FILTER (WHERE r.status = 'approved'), 0) AS approved,
       coalesce(sum(r.rAmount) FILTER (WHERE r.status = 'pending'), 0) AS pending,
       c.cAmount - coalesce(sum(r.rAmount)
           FILTER (WHERE r.status IN ('pending', 'approved')), 0) AS refundable_balance
FROM gym.Contract c LEFT JOIN gym.Refund r USING (cNo)
GROUP BY c.cNo ORDER BY c.cNo;

-- Q13 每月收退款：合約按簽約日入帳；核准退款按申請日分組。
-- ERD 沒有付款日／核准日，因此這只是展示用收款統計，非正式會計收入認列。
WITH flows AS (
    SELECT date_trunc('month', cDate::timestamp)::date AS month,
           cAmount AS collected, 0::numeric AS refunded FROM gym.Contract
    UNION ALL
    SELECT date_trunc('month', rDate::timestamp)::date, 0::numeric, rAmount
    FROM gym.Refund WHERE status = 'approved'
)
SELECT month, sum(collected) AS collected, sum(refunded) AS refunded,
       sum(collected) - sum(refunded) AS net_cash_flow
FROM flows GROUP BY month ORDER BY month;

-- Q14 課程熱門程度、出席率；零分母用 NULL 表示尚無可統計的點名。
SELECT c.coNo, c.coName, c.capacity,
       count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled') AS occupied,
       round(100.0 * count(b.mId) FILTER (WHERE b.bStatus <> 'cancelled')
             / c.capacity, 2) AS occupancy_pct,
       count(b.mId) FILTER (WHERE b.bStatus = 'attended') AS attended,
       round(100.0 * count(b.mId) FILTER (WHERE b.bStatus = 'attended')
             / nullif(count(b.mId) FILTER (WHERE b.bStatus IN ('attended', 'absent')), 0), 2)
           AS attendance_pct
FROM gym.Course c LEFT JOIN gym.Booking b USING (coNo)
GROUP BY c.coNo ORDER BY occupied DESC, c.coNo;

-- Q15 系統總覽。使用獨立子查詢，避免不同一對多關係交叉相乘。
SELECT (SELECT count(*) FROM gym.Member) AS members,
       (SELECT count(*) FROM gym.Trainer) AS trainers,
       (SELECT count(*) FROM gym.Course) AS courses,
       (SELECT count(*) FROM gym.Booking b JOIN gym.Course c USING (coNo)
        WHERE b.bStatus = 'booked'
          AND ((c.coDate + c.startTime) AT TIME ZONE 'Asia/Taipei') > CURRENT_TIMESTAMP)
           AS upcoming_reservations,
       (SELECT coalesce(sum(cAmount), 0) FROM gym.Contract) AS gross_collected,
       (SELECT coalesce(sum(rAmount), 0) FROM gym.Refund WHERE status = 'approved') AS approved_refunds;

-- W01 新增會員、更新資料、增刪聯絡電話。
INSERT INTO gym.Member (mId, email, mName, sex, birthday)
VALUES ('M_DEMO', 'demo@example.com', '測試會員', 'F', DATE '1999-05-20');
UPDATE gym.Member SET email = 'demo.updated@example.com'
WHERE mId = 'M_DEMO' RETURNING *;
INSERT INTO gym.MemPhone (mPhone, mId) VALUES ('0933000001', 'M_DEMO');
INSERT INTO gym.MemPhone (mPhone, mId) VALUES ('02-20000000', 'M_DEMO');
DELETE FROM gym.MemPhone WHERE mId = 'M_DEMO' AND mPhone = '02-20000000';

-- W02 新增教練、指定主管、分派／解除會員與教練關係。
INSERT INTO gym.Trainer (tId, history, tPhone, tName, speciality, leader)
VALUES ('T_DEMO', '新進教練', '0911333444', '測試教練', '基礎訓練', 'T001');
UPDATE gym.Trainer SET leader = 'T002' WHERE tId = 'T_DEMO';
INSERT INTO gym.AssignedTo (mId, tId) VALUES ('M_DEMO', 'T_DEMO')
ON CONFLICT (mId, tId) DO NOTHING;
DELETE FROM gym.AssignedTo WHERE mId = 'M_DEMO' AND tId = 'T_DEMO';
INSERT INTO gym.AssignedTo (mId, tId) VALUES ('M_DEMO', 'T001');

-- W03 新增／調整方案；價格調整不回寫已簽約的 cAmount。
INSERT INTO gym.Plan (pId, pName, duration, price)
VALUES ('P_DEMO', '兩週練習方案', 14, 800);
UPDATE gym.Plan SET price = 850 WHERE pId = 'P_DEMO' RETURNING *;

-- W04 簽約：將當時方案價格存入 cAmount，依天數產生含首尾日的到期日。
INSERT INTO gym.Contract (cNo, cDate, startDate, endDate, cAmount, paymentMethod, pId, mId)
SELECT 'C_DEMO', CURRENT_DATE, CURRENT_DATE, CURRENT_DATE + p.duration - 1,
       p.price, 'credit_card', p.pId, 'M_DEMO'
FROM gym.Plan p WHERE p.pId = 'P_DEMO' RETURNING *;

-- W05 建立／修改課程。
INSERT INTO gym.Course (coNo, coName, capacity, location, coDate, startTime, endTime, tId)
VALUES ('CO_DEMO', '新手訓練示範', 2, '教室 A', CURRENT_DATE + 1, TIME '12:00', TIME '13:00', 'T_DEMO');
UPDATE gym.Course SET location = '教室 B', capacity = 3
WHERE coNo = 'CO_DEMO' RETURNING *;

-- W06 預約：先鎖課程，再在下一個 SQL 指令寫入；觸發器再次檢查容量。
-- 課程已開始就不新增（RETURNING 會是 0 列）；本範例不要求另有有效合約。
SELECT coNo FROM gym.Course WHERE coNo = 'CO_DEMO' FOR UPDATE;
INSERT INTO gym.Booking (coNo, mId, bStatus, bookingTime)
SELECT c.coNo, 'M_DEMO', 'booked', CURRENT_TIMESTAMP FROM gym.Course c
WHERE c.coNo = 'CO_DEMO'
  AND ((c.coDate + c.startTime) AT TIME ZONE 'Asia/Taipei') > CURRENT_TIMESTAMP
RETURNING *;

-- W07 取消預約；保留該會員／課程的唯一一筆資料。
UPDATE gym.Booking SET bStatus = 'cancelled'
WHERE coNo = 'CO_DEMO' AND mId = 'M_DEMO' AND bStatus = 'booked'
RETURNING *;
-- 重新預約：更新原列，不另外新增歷程表。容量仍由觸發器驗證。
SELECT coNo FROM gym.Course WHERE coNo = 'CO_DEMO' FOR UPDATE;
UPDATE gym.Booking b SET bStatus = 'booked', bookingTime = CURRENT_TIMESTAMP
FROM gym.Course c
WHERE b.coNo = c.coNo AND b.coNo = 'CO_DEMO' AND b.mId = 'M_DEMO'
  AND b.bStatus = 'cancelled'
  AND ((c.coDate + c.startTime) AT TIME ZONE 'Asia/Taipei') > CURRENT_TIMESTAMP
RETURNING b.*;

-- W08 點名（只對已結束的課程）；可改為 absent。
UPDATE gym.Booking b SET bStatus = 'attended'
FROM gym.Course c WHERE c.coNo = b.coNo AND b.coNo = 'CO007'
  AND b.mId = 'M003' AND b.bStatus IN ('booked', 'absent')
  AND ((c.coDate + c.endTime) AT TIME ZONE 'Asia/Taipei') <= CURRENT_TIMESTAMP
RETURNING b.*;

-- W09 申請退款：先鎖合約，下一個指令才取 MAX+1。
-- 所有序號產生端都要遵守此流程；不能單獨用未加鎖的 MAX+1。
SELECT cNo FROM gym.Contract WHERE cNo = 'C_DEMO' FOR UPDATE;
INSERT INTO gym.Refund (rNo, cNo, rAmount, rDate, status, reason)
SELECT coalesce(max(rNo), 0) + 1, 'C_DEMO', 100, CURRENT_DATE, 'pending', '示範部分退款'
FROM gym.Refund WHERE cNo = 'C_DEMO' RETURNING *;

-- W10 審核退款：只處理待審案件。重複核准不會再次更新。
UPDATE gym.Refund SET status = 'approved'
WHERE rNo = 1 AND cNo = 'C_DEMO' AND status = 'pending' RETURNING *;
-- 駁回用法（本例已核准，所以此指令更新 0 列）。
UPDATE gym.Refund SET status = 'rejected'
WHERE rNo = 1 AND cNo = 'C_DEMO' AND status = 'pending' RETURNING *;

-- W11 刪除無歷史資料的示範對象：有合約／預約／退款的對象受 RESTRICT 保護。
INSERT INTO gym.Member (mId, email, mName, sex, birthday)
VALUES ('M_UNUSED', 'unused@example.com', '待刪測試會員', 'M', DATE '2000-01-01');
INSERT INTO gym.MemPhone (mPhone, mId) VALUES ('0900000000', 'M_UNUSED');
INSERT INTO gym.AssignedTo (mId, tId) VALUES ('M_UNUSED', 'T001');
DELETE FROM gym.Member WHERE mId = 'M_UNUSED' RETURNING *;
-- 上一步連動刪除該會員電話與教練分派資料。
INSERT INTO gym.Plan (pId, pName, duration, price) VALUES ('P_UNUSED', '未售方案', 1, 0);
DELETE FROM gym.Plan WHERE pId = 'P_UNUSED' RETURNING *;

-- 全部寫入示範回滾；01、02 建立的結構與資料不受影響。
ROLLBACK;
