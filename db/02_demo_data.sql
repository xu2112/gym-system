-- 測試資料只載入一次；相同 ID 再載入會失敗，整份交易回滾。
BEGIN;
SET LOCAL TIME ZONE 'Asia/Taipei';

INSERT INTO gym.Member (mId, email, mName, sex, birthday) VALUES
('M001', 'yuting@example.com', '徐毓廷', 'F', DATE '2004-04-21'),
('M002', 'chihming@example.com', '陳志明', 'M', DATE '1990-08-23'),
('M003', 'yuchen@example.com', '王宇辰', 'M', DATE '2000-01-08'),
('M004', 'hsinyi@example.com', '張欣怡', 'F', DATE '1998-11-16'),
('M005', 'pohan@example.com', '李柏翰', 'M', DATE '1987-06-02'),
('M006', 'chiaen@example.com', '吳佳恩', 'F', DATE '2002-09-09'),
('M007', 'szuan@example.com', '劉思安', 'M', DATE '1993-12-20'),
('M008', 'meiling@example.com', '黃美玲', 'F', DATE '1985-04-18');

-- 先建主管，再建助理教練，符合自我參照 FK。
INSERT INTO gym.Trainer (tId, history, tPhone, tName, speciality, leader) VALUES
('T001', '十年體能訓練經驗', '0911000001', '周建宏', '肌力與體能', NULL);
INSERT INTO gym.Trainer (tId, history, tPhone, tName, speciality, leader) VALUES
('T002', '六年瑜珈教學經驗', '0911000002', '許若晴', '瑜珈與伸展', 'T001'),
('T003', '五年有氧教學經驗', '0911000003', '鄭凱文', '飛輪與有氧', 'T001'),
('T004', '三年核心訓練經驗', '0911000004', '蔡宜蓁', '皮拉提斯與核心', 'T002');

INSERT INTO gym.Plan (pId, pName, duration, price) VALUES
('P001', '月度入門', 30, 1500.00),
('P002', '季度標準', 90, 4200.00),
('P003', '年度全館', 365, 15000.00),
('P004', '七日體驗', 7, 500.00);

INSERT INTO gym.Course (coNo, coName, capacity, location, coDate, startTime, endTime, tId) VALUES
('CO001', '基礎肌力', 3, '重訓教室 A', CURRENT_DATE + 1, TIME '18:00', TIME '19:00', 'T001'),
('CO002', '舒緩瑜珈', 2, '瑜珈教室', CURRENT_DATE + 2, TIME '19:00', TIME '20:00', 'T002'),
('CO003', '燃脂飛輪', 6, '飛輪教室', CURRENT_DATE + 3, TIME '18:30', TIME '19:20', 'T003'),
('CO004', '核心皮拉提斯', 5, '多功能教室', CURRENT_DATE + 5, TIME '10:00', TIME '11:00', 'T004'),
('CO005', '進階肌力', 4, '重訓教室 A', CURRENT_DATE + 7, TIME '18:00', TIME '19:00', 'T001'),
('CO006', '週末伸展', 8, '瑜珈教室', CURRENT_DATE + 10, TIME '09:00', TIME '10:00', 'T002'),
('CO007', '有氧循環', 6, '多功能教室', CURRENT_DATE - 2, TIME '19:00', TIME '20:00', 'T003'),
('CO008', '新手體能', 10, '重訓教室 B', CURRENT_DATE + 14, TIME '14:00', TIME '15:00', 'T001');

INSERT INTO gym.MemPhone (mPhone, mId) VALUES
('0922000001', 'M001'), ('02-23456789', 'M001'),
('0922000002', 'M002'), ('0922000003', 'M003'),
('0922000004', 'M004'), ('0922000005', 'M005'),
('0922000006', 'M006'), ('0922000007', 'M007'), ('0922000008', 'M008');

INSERT INTO gym.Contract (cNo, cDate, startDate, endDate, cAmount, paymentMethod, pId, mId) VALUES
('C001', CURRENT_DATE - 10, CURRENT_DATE - 10, CURRENT_DATE + 19, 1500, 'credit_card', 'P001', 'M001'),
('C002', CURRENT_DATE - 20, CURRENT_DATE - 20, CURRENT_DATE + 69, 4200, 'bank_transfer', 'P002', 'M002'),
('C003', CURRENT_DATE - 30, CURRENT_DATE - 30, CURRENT_DATE + 334, 15000, 'credit_card', 'P003', 'M003'),
('C004', CURRENT_DATE - 25, CURRENT_DATE - 25, CURRENT_DATE + 4, 1500, 'cash', 'P001', 'M004'),
('C005', CURRENT_DATE - 100, CURRENT_DATE - 100, CURRENT_DATE - 11, 4200, 'bank_transfer', 'P002', 'M005'),
('C006', CURRENT_DATE - 2, CURRENT_DATE - 2, CURRENT_DATE + 4, 500, 'cash', 'P004', 'M006'),
('C007', CURRENT_DATE - 5, CURRENT_DATE - 5, CURRENT_DATE + 24, 1350, 'credit_card', 'P001', 'M007'),
('C008', CURRENT_DATE, CURRENT_DATE + 5, CURRENT_DATE + 94, 4200, 'bank_transfer', 'P002', 'M008'),
('C009', CURRENT_DATE - 50, CURRENT_DATE - 50, CURRENT_DATE - 21, 1500, 'cash', 'P001', 'M001');

INSERT INTO gym.Refund (rNo, cNo, rAmount, rDate, status, reason) VALUES
(1, 'C005', 800, CURRENT_DATE - 12, 'approved', '搬遷，申請部分退費'),
(2, 'C005', 200, CURRENT_DATE - 10, 'rejected', '額外退費申請未通過'),
(1, 'C007', 300, CURRENT_DATE - 1, 'pending', '工作異動，申請部分退費'),
(1, 'C009', 500, CURRENT_DATE - 22, 'approved', '傷後休養，協議退費'),
(2, 'C009', 200, CURRENT_DATE - 21, 'approved', '補充核准退費');

INSERT INTO gym.Booking (coNo, mId, bStatus, bookingTime) VALUES
('CO001', 'M001', 'booked', CURRENT_TIMESTAMP - INTERVAL '2 days'),
('CO001', 'M002', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO001', 'M003', 'cancelled', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO002', 'M001', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO002', 'M004', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO003', 'M002', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO003', 'M003', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO004', 'M006', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO005', 'M007', 'booked', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CO007', 'M001', 'attended', CURRENT_TIMESTAMP - INTERVAL '5 days'),
('CO007', 'M002', 'attended', CURRENT_TIMESTAMP - INTERVAL '4 days'),
('CO007', 'M003', 'absent', CURRENT_TIMESTAMP - INTERVAL '4 days'),
('CO007', 'M005', 'cancelled', CURRENT_TIMESTAMP - INTERVAL '3 days');

INSERT INTO gym.AssignedTo (mId, tId) VALUES
('M001', 'T001'), ('M001', 'T002'), ('M002', 'T001'),
('M003', 'T003'), ('M004', 'T002'), ('M005', 'T001'),
('M006', 'T004'), ('M007', 'T003'), ('M008', 'T004');
COMMIT;
