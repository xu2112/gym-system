-- 登入帳號表：在 project_14 執行一次（01～04 都完成之後）
-- 管理者帳號：admin / admin1234
-- 會員帳號：m001 ～ m008，密碼都是 1234（對應會員 M001 ～ M008）
BEGIN;

CREATE TABLE gym.account (
    account   VARCHAR(30)  PRIMARY KEY,
    password  VARCHAR(200) NOT NULL,
    identity  VARCHAR(10)  NOT NULL CHECK (identity IN ('manager', 'member')),
    mId       VARCHAR(10)  UNIQUE,
    FOREIGN KEY (mId) REFERENCES gym.member(mId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CHECK ((identity = 'member' AND mId IS NOT NULL) OR (identity = 'manager' AND mId IS NULL))
);

INSERT INTO gym.account (account, password, identity, mId) VALUES
('admin', 'pbkdf2:sha256:600000$FgWvNvqvdYrTckfi$7e1b05594e3a29e10b887c43f5bebfb52cdf5ece4ba6177cb7054019f2afedec', 'manager', NULL),
('m001', 'pbkdf2:sha256:600000$YrNfJObrwcpnBxlO$e8624527a9adff8a545d3eebfab362acab8a8e8f9e7a8ed338c58f2ccbbb4bc7', 'member', 'M001'),
('m002', 'pbkdf2:sha256:600000$DxYNj81bkzgaOQnL$6874fd3810750f75adfcdb8d345e4c1e84697f94c23ba84b51f35b207242bac0', 'member', 'M002'),
('m003', 'pbkdf2:sha256:600000$MjzArdE71LTFxEh2$5fe8c2efff62b83fb72095d8a1ca7c93637a56ed38f49f8f5cc149be8a4e685c', 'member', 'M003'),
('m004', 'pbkdf2:sha256:600000$W2Krah3IHnsqrEBI$69f0f3ac437580620af808437f91f2e57eb78eba34423df90a52c25d48bdb2d1', 'member', 'M004'),
('m005', 'pbkdf2:sha256:600000$Oh34tRwMdycgxpP9$eedec22b6a889b3cbe52f91615c1ee4ba1dce643a6ed94995417e61a40ffe741', 'member', 'M005'),
('m006', 'pbkdf2:sha256:600000$ARqbHgatxU7eNsgd$46b38118ae2bcdc4dc10389e44547c687d56fa9a23acc4fa88752c45173a9097', 'member', 'M006'),
('m007', 'pbkdf2:sha256:600000$X7xrM7VhJxLSYYKo$d4b304a8e46ebc6317f4d0fb0ae72071fc5de137504806951be6c3e5ab0cfbb2', 'member', 'M007'),
('m008', 'pbkdf2:sha256:600000$2cVc6MPSueGAYTbs$633afcd5e57dbddc240ace84a3a8d2b26eaee656bb1d80c74c4257ccb2433183', 'member', 'M008');

COMMIT;