-- 01 建立 gym schema 與 9 張表（全新資料庫才需要執行）
CREATE SCHEMA IF NOT EXISTS gym;
SET search_path TO gym;

-- =========================================
-- 健身房管理系統 PostgreSQL 建表 SQL
-- 依參照順序建立：被參照的表先建
-- =========================================

-- 1. Trainer（教練）
--    leader：自身參照，表示這位教練的領導教練（lead 關係，1:N）
CREATE TABLE Trainer (
    tId         VARCHAR(10) PRIMARY KEY,
    tName       VARCHAR(50) NOT NULL,
    tPhone      VARCHAR(20),
    speciality  VARCHAR(100),
    history     TEXT,
    leader      VARCHAR(10),
    FOREIGN KEY (leader) REFERENCES Trainer(tId)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

-- 2. Member（會員）
CREATE TABLE Member (
    mId       VARCHAR(10) PRIMARY KEY,
    mName     VARCHAR(50) NOT NULL,
    email     VARCHAR(100) UNIQUE,
    sex       CHAR(1) CHECK (sex IN ('M', 'F')),
    birthday  DATE
);

-- 3. MemPhone（會員電話，多值屬性拆出的表）
CREATE TABLE MemPhone (
    mPhone  VARCHAR(20) PRIMARY KEY,
    mId     VARCHAR(10) NOT NULL,
    FOREIGN KEY (mId) REFERENCES Member(mId)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 4. Plan（方案）
CREATE TABLE Plan (
    pId       VARCHAR(10) PRIMARY KEY,
    pName     VARCHAR(50) NOT NULL,
    duration  INT NOT NULL CHECK (duration > 0),          -- 期間（例如月數）
    price     NUMERIC(10, 2) NOT NULL CHECK (price >= 0)
);

-- 5. Course（課程）
--    tId：授課教練（Teach 關係，N:1，每門課一定有教練）
CREATE TABLE Course (
    coNo       VARCHAR(10) PRIMARY KEY,
    coName     VARCHAR(50) NOT NULL,
    capacity   INT NOT NULL CHECK (capacity > 0),
    location   VARCHAR(50),
    coDate     DATE NOT NULL,
    startTime  TIME NOT NULL,
    endTime    TIME NOT NULL,
    tId        VARCHAR(10) NOT NULL,
    CHECK (endTime > startTime),
    FOREIGN KEY (tId) REFERENCES Trainer(tId)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- 6. Contract（合約）
--    mId：簽約會員（Sign 關係）
--    pId：合約方案（Include 關係）
CREATE TABLE Contract (
    cNo            VARCHAR(10) PRIMARY KEY,
    cDate          DATE NOT NULL,
    startDate      DATE NOT NULL,
    endDate        DATE NOT NULL,
    cAmount        NUMERIC(10, 2) NOT NULL CHECK (cAmount >= 0),
    paymentMethod  VARCHAR(20),
    pId            VARCHAR(10) NOT NULL,
    mId            VARCHAR(10) NOT NULL,
    CHECK (endDate >= startDate),
    FOREIGN KEY (pId) REFERENCES Plan(pId)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    FOREIGN KEY (mId) REFERENCES Member(mId)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- 7. Refund（退款，弱實體）
--    主鍵 = 部分鍵 rNo + 擁有者 Contract 的 cNo
CREATE TABLE Refund (
    rNo      VARCHAR(10),
    cNo      VARCHAR(10),
    rAmount  NUMERIC(10, 2) NOT NULL CHECK (rAmount >= 0),
    rDate    DATE NOT NULL,
    status   VARCHAR(20),
    reason   TEXT,
    PRIMARY KEY (rNo, cNo),
    FOREIGN KEY (cNo) REFERENCES Contract(cNo)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 8. Booking（會員預約課程，M:N 關係）
CREATE TABLE Booking (
    coNo         VARCHAR(10),
    mId          VARCHAR(10),
    bStatus      VARCHAR(20),
    bookingTime  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (coNo, mId),
    FOREIGN KEY (coNo) REFERENCES Course(coNo)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (mId) REFERENCES Member(mId)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 9. AssignedTo（會員指派教練，M:N 關係）
CREATE TABLE AssignedTo (
    mId  VARCHAR(10),
    tId  VARCHAR(10),
    PRIMARY KEY (mId, tId),
    FOREIGN KEY (mId) REFERENCES Member(mId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (tId) REFERENCES Trainer(tId)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
