-- 補強 schema：在 project_14 執行一次即可（02 假資料放好之後）
BEGIN;

-- 1. Refund.rNo 改成整數：退款序號 1, 2, 3…，W09 才能用 MAX + 1 產生下一號
ALTER TABLE gym.refund ALTER COLUMN rno TYPE INT USING rno::int;

-- 2. 課程名額檢查：預約（或重新預約）時，有效預約人數不能超過 capacity
CREATE OR REPLACE FUNCTION gym.check_course_capacity()
RETURNS trigger AS $$
DECLARE
    cap  INT;
    used INT;
BEGIN
    IF NEW.bStatus = 'cancelled' THEN
        RETURN NEW;               -- 取消預約不佔名額，不用檢查
    END IF;

    -- 鎖住課程，避免兩人同時搶最後一個名額
    SELECT capacity INTO cap FROM gym.course WHERE coNo = NEW.coNo FOR UPDATE;

    SELECT count(*) INTO used
    FROM gym.booking
    WHERE coNo = NEW.coNo
      AND bStatus <> 'cancelled'
      AND mId <> NEW.mId;         -- 不算自己這一筆（修改時）

    IF used >= cap THEN
        RAISE EXCEPTION '課程 % 已額滿（名額 %）', NEW.coNo, cap;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_booking_capacity ON gym.booking;
CREATE TRIGGER trg_booking_capacity
BEFORE INSERT OR UPDATE OF bStatus, coNo ON gym.booking
FOR EACH ROW EXECUTE FUNCTION gym.check_course_capacity();

COMMIT;
