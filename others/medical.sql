CREATE DATABASE IF NOT EXISTS medical;

DROP TABLE IF EXISTS feedback;

DROP TABLE IF EXISTS inpatient_record;

DROP TABLE IF EXISTS inpatient_booking;

DROP TABLE IF EXISTS examination_report;

DROP TABLE IF EXISTS examination_booking;

DROP TABLE IF EXISTS emr;

DROP TABLE IF EXISTS appointment;

DROP TABLE IF EXISTS examination_item;

DROP TABLE IF EXISTS doctor_schedule;

DROP TABLE IF EXISTS doctor_department;

DROP TABLE IF EXISTS doctor;

DROP TABLE IF EXISTS department;

DROP TABLE IF EXISTS shift_item;

DROP TABLE IF EXISTS patient;

CREATE TABLE patient (
    id bigint auto_increment comment "患者id",
    name varchar(50) NOT NULL comment "患者名称",
    phone varchar(20) NOT NULL comment "患者电话",
    gender varchar(20) DEFAULT 0 comment "性别(未知 男 女)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id)
) comment "患者信息表";

CREATE TABLE shift_item (
    name varchar(20) comment "班次类型名称",
    description varchar(255) comment "班次描述",
    schedule json NOT NULL comment "班次安排",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (name)
) comment "科室值班类型表";

CREATE TABLE department (
    id bigint auto_increment comment "科室id",
    name varchar(50) NOT NULL comment "科室名称",
    parent_id bigint DEFAULT NULL comment "上级科室id(用于二级科室指向一级科室)",
    dept_level tinyint DEFAULT 1 comment "科室级别(1=一级科室，2=级科室)",
    is_clinical tinyint DEFAULT 1 comment "是否为临床科室(0=否，1=是)",
    can_register tinyint DEFAULT 1 comment "是否可用于患者挂号(0=否，1=是)",
    shift_type_name varchar(20) comment "值班类型名称",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (parent_id) REFERENCES department (id),
    FOREIGN KEY (shift_type_name) REFERENCES shift_item (name)
) comment "科室信息表";

CREATE TABLE doctor (
    id bigint auto_increment comment "医生id",
    name varchar(50) comment "医生名称",
    title varchar(20) comment "职称",
    phone varchar(20) comment "医生电话",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id)
) comment "医生信息表";

CREATE TABLE doctor_department (
    id bigint auto_increment,
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    dept_id bigint NOT NULL comment "科室id",
    dept_name varchar(50) NOT NULL comment "科室名称",
    is_primary tinyint NOT NULL comment "是否为主属科室(0=否，1=是)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint(1) DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (doctor_id) REFERENCES doctor (id),
    FOREIGN KEY (dept_id) REFERENCES department (id)
) comment "医生科室关联表";

CREATE TABLE doctor_schedule (
    id bigint auto_increment comment "排班信息id",
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    dept_id bigint NOT NULL comment "科室id",
    dept_name varchar(50) NOT NULL comment "科室名称",
    shift_no bigint comment "班次号",
    schedule_date DATE NOT NULL comment "排班日期",
    start_datetime datetime NOT NULL comment "开始时间",
    end_datetime datetime NOT NULL comment "结束时间",
    appointment_limit int comment "挂号数上限",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (doctor_id) REFERENCES doctor (id),
    FOREIGN KEY (dept_id) REFERENCES department (id)
) comment "医生排班信息表";

CREATE TABLE appointment (
    id bigint auto_increment comment "挂号id",
    patient_id bigint NOT NULL comment "患者id",
    patient_name varchar(50) NOT NULL comment "患者名称",
    dept_id bigint NOT NULL comment "科室id",
    dept_name varchar(50) NOT NULL comment "科室名称",
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    shift_no bigint NOT NULL comment "班次号",
    visit_date DATE NOT NULL comment "预约日期",
    schedule_id bigint NOT NULL comment "排班id",
    start_datetime datetime NOT NULL comment "开始时间",
    end_datetime datetime NOT NULL comment "结束时间",
    queue_no int comment "当天序号",
    status tinyint comment "预约状态(1=已预约 2=已取号 3=已取消)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint(1) DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (schedule_id) REFERENCES doctor_schedule (id)
) comment "挂号表";

CREATE TABLE emr (
    id bigint auto_increment comment "病历id",
    patient_id bigint NOT NULL comment "患者id",
    patient_name varchar(50) NOT NULL comment "患者名称",
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    case_id varchar(100) NOT NULL comment "治疗流程编号",
    visit_type varchar(20) NOT NULL comment "就诊类型(门诊、住院、急诊)",
    emr_type varchar(20) NOT NULL comment "病历类型(首诊病历、随访病历、出院小结)",
    content json comment "结构化病历JSON，可存主诉/现病史/诊断/处方",
    signature json comment "电子签名",
    `version` bigint DEFAULT 1 comment "版本号(用于追踪病历修改历史)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    UNIQUE (case_id, emr_type, `version`),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (doctor_id) REFERENCES doctor (id)
) comment "电子病历表";

CREATE TABLE examination_item (
    id bigint auto_increment comment "检查项目序号",
    name varchar(100) NOT NULL comment "检查项目名称",
    price decimal(8, 2) comment "价格",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id)
) comment "检查项目字典";

CREATE TABLE examination_booking (
    id bigint auto_increment comment "检查预约id",
    patient_id bigint NOT NULL comment "患者id",
    patient_name varchar(50) NOT NULL comment "患者名称",
    examination_item_id bigint NOT NULL comment "检查项目id",
    examination_item_name varchar(100) comment "检查项目名称",
    examination_date DATE NOT NULL comment "预约检查日期",
    start_datetime datetime NOT NULL comment "开始时间",
    end_datetime datetime NOT NULL comment "结束时间",
    queue_no int comment "当天序号",
    status tinyint comment "预约状态(1=已预约 2=已检查 3=已取消)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (examination_item_id) REFERENCES examination_item (id)
) comment "检查预约表";

CREATE TABLE examination_report (
    id bigint auto_increment comment "检查报告id",
    patient_id bigint comment "患者id",
    patient_name varchar(50) comment "患者名称",
    examination_item_id bigint comment "检查项目id",
    examination_item_name varchar(100) comment "检查项目名称",
    examination_date DATE comment "检查日期",
    examination_time DATETIME comment "检查时间",
    pdf_url varchar(255) comment "检查报告pdf链接",
    summary text comment "总结",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (examination_item_id) REFERENCES examination_item (id)
) comment "检查报告表";

CREATE TABLE inpatient_booking (
    id bigint auto_increment comment "住院预约id",
    patient_id bigint NOT NULL comment "患者id",
    patient_name varchar(50) NOT NULL comment "患者名称",
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    dept_id bigint NOT NULL comment "科室id",
    dept_name varchar(50) NOT NULL comment "科室名称",
    expected_date DATE comment "入院日期",
    bed_type tinyint comment "病床类型(1=普通 2=单人间 3=ICU)",
    status tinyint comment "预约状态(1=排队中 2=已预约 3=已入院 4=已取消)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (doctor_id) REFERENCES doctor (id),
    FOREIGN KEY (dept_id) REFERENCES department (id)
) comment "住院预约表";

CREATE TABLE inpatient_record (
    id bigint auto_increment comment "住院记录id",
    patient_id bigint NOT NULL comment "患者id",
    patient_name varchar(50) NOT NULL comment "患者名称",
    dept_id bigint NOT NULL comment "科室id",
    dept_name varchar(50) NOT NULL comment "科室名称",
    doctor_id bigint NOT NULL comment "医生id",
    doctor_name varchar(50) NOT NULL comment "医生名称",
    bed_type tinyint comment "病床类型(1=普通 2=单人间 3=ICU)",
    bed_no bigint comment "床位号",
    admission_time datetime comment "入院时间",
    discharge_time datetime comment "出院时间",
    status tinyint comment "住院状态(1=在院 2=已出院)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id),
    FOREIGN KEY (dept_id) REFERENCES department (id),
    FOREIGN KEY (doctor_id) REFERENCES doctor (id)
) comment "住院记录表";

CREATE TABLE feedback (
    id bigint auto_increment comment "反馈信息id",
    patient_id bigint comment "反馈患者id",
    type varchar(20) comment "建议类型(建议 系统故障)",
    title varchar(255) comment "反馈标题",
    content text comment "反馈内容",
    pic_urls json comment "反馈图片链接JSON数组",
    status tinyint comment "处理状态(1=待处理 2=已处理)",
    create_time datetime DEFAULT CURRENT_TIMESTAMP comment "创建时间",
    update_time datetime ON UPDATE CURRENT_TIMESTAMP comment "修改时间",
    is_deleted tinyint(1) DEFAULT 0 comment "是否删除(0=未删除，1=已删除)",
    PRIMARY KEY (id),
    FOREIGN KEY (patient_id) REFERENCES patient (id)
) comment "信息反馈表";

-- 添加值班类型信息
INSERT INTO
    shift_item (
        `name`,
        `description`,
        `schedule`
    )
VALUES (
        "outpatient",
        "门诊日班",
        '[
            {"start": "08:00","end": "12:00"},
            {"start": "14:00","end": "18:00"}
        ]'
    ),
    (
        "outpatient-oncall",
        "门诊日班+夜间值班",
        '[
            {"start": "08:00","end": "12:00"},
            {"start": "14:00","end": "18:00"},
            {"start": "18:00","end": "08:00"}
        ]'
    ),
    (
        "24h-3",
        "24小时三班倒",
        '[
            {"start": "00:00","end": "08:00"},
            {"start": "08:00","end": "16:00"},
            {"start": "16:00","end": "00:00"}
        ]'
    ),
    (
        "24h-2",
        "24小时两班倒",
        '[
            {"start": "08:00","end": "20:00"},
            {"start": "20:00","end": "08:00"}
        ]'
    );

-- 添加科室信息
--  一级科室
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register,
        shift_type_name
    )
VALUES (
        "内科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "外科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "骨科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "妇产科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "儿科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "皮肤科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "眼科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "耳鼻喉科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "口腔科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "肿瘤科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "中医科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "精神心理科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "营养科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    (
        "康复科",
        NULL,
        1,
        1,
        1,
        "outpatient"
    ),
    ("急诊科", NULL, 1, 1, 1, "24h-3"),
    ("重症医学科", NULL, 1, 1, 0, NULL),
    ("麻醉科", NULL, 1, 1, 0, NULL),
    ("医学影像科", NULL, 1, 0, 0, NULL),
    ("护理科", NULL, 1, 0, 0, NULL),
    ("药剂科", NULL, 1, 0, 0, NULL),
    ("输血科", NULL, 1, 0, 0, NULL),
    ("病理科", NULL, 1, 0, 0, NULL),
    ("设备科", NULL, 1, 0, 0, NULL),
    ("信息科", NULL, 1, 0, 0, NULL),
    ("公共卫生科", NULL, 1, 0, 0, NULL);
--  二级科室-内科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "内科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "普通内科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "心内科", 2, 1, 1
        UNION ALL
        SELECT "呼吸内科", 2, 1, 1
        UNION ALL
        SELECT "消化内科", 2, 1, 1
        UNION ALL
        SELECT "肾内科", 2, 1, 1
        UNION ALL
        SELECT "内分泌科", 2, 1, 1
        UNION ALL
        SELECT "神经内科", 2, 1, 1
        UNION ALL
        SELECT "血液内科", 2, 1, 1
        UNION ALL
        SELECT "风湿免疫内科", 2, 1, 1
        UNION ALL
        SELECT "感染内科", 2, 1, 1
    ) AS t;
--  二级科室-外科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "外科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "普通外科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "神经外科", 2, 1, 1
        UNION ALL
        SELECT "泌尿外科", 2, 1, 1
        UNION ALL
        SELECT "胸外科", 2, 1, 1
        UNION ALL
        SELECT "心外科", 2, 1, 1
        UNION ALL
        SELECT "肝脏外科", 2, 1, 1
        UNION ALL
        SELECT "血管外科", 2, 1, 1
        UNION ALL
        SELECT "乳腺外科", 2, 1, 1
        UNION ALL
        SELECT "整形外科", 2, 1, 1
    ) AS t;
-- 二级科室 - 骨科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "骨科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "骨科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 妇产科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "妇产科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "妇科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "产科", 2, 1, 1
        UNION ALL
        SELECT "妇科内分泌", 2, 1, 1
    ) AS t;
-- 二级科室 - 儿科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "儿科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "儿科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 皮肤科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "皮肤科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "皮肤性病科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "皮科激光中心", 2, 1, 1
        UNION ALL
        SELECT "皮科门诊", 2, 1, 1
    ) AS t;
-- 二级科室 - 眼科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "眼科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "眼科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 耳鼻喉科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "耳鼻喉科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "耳鼻喉科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 口腔科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "口腔科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "口腔科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 肿瘤科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "肿瘤科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "肿瘤内科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "肿瘤外科", 2, 1, 1
        UNION ALL
        SELECT "妇科肿瘤", 2, 1, 1
    ) AS t;
-- 二级科室 - 中医科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "中医科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "中医科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 精神心理科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "精神心理科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "精神科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "心理科", 2, 1, 1
        UNION ALL
        SELECT "临床心理门诊", 2, 1, 1
        UNION ALL
        SELECT "儿童心理科", 2, 1, 1
    ) AS t;
-- 二级科室 - 营养科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "营养科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "临床营养科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
    ) AS t;
-- 二级科室 - 康复科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "康复科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "神经康复科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "骨关节康复科", 2, 1, 1
        UNION ALL
        SELECT "儿童康复科", 2, 1, 1
        UNION ALL
        SELECT "疼痛康复科", 2, 1, 1
        UNION ALL
        SELECT "心肺康复科", 2, 1, 1
    ) AS t;
-- 二级科室 - 急诊科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "急诊科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "急诊内科" AS name, 2 AS dept_level, 1 AS is_clinical, 1 AS can_register
        UNION ALL
        SELECT "急诊外科", 2, 1, 1
        UNION ALL
        SELECT "重症急诊", 2, 1, 1
    ) AS t;
-- 二级科室 - 重症医学科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "重症医学科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "重症医学科" AS name, 2 AS dept_level, 1 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 麻醉科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "麻醉科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "麻醉科" AS name, 2 AS dept_level, 1 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 医学影像科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "医学影像科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "放射科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
        UNION ALL
        SELECT "超声科", 2, 0, 0
        UNION ALL
        SELECT "核医学科", 2, 0, 0
        UNION ALL
        SELECT "介入放射科", 2, 0, 0
    ) AS t;
-- 二级科室 - 护理科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "护理科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "护理科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 药剂科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "药剂科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "药剂科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 输血科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "输血科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "输血科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 病理科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "病理科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "病理科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 设备科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "设备科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "设备科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 信息科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "信息科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "信息科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 二级科室 - 公共卫生科下属
INSERT INTO
    department (
        name,
        parent_id,
        dept_level,
        is_clinical,
        can_register
    )
SELECT t.name, (
        SELECT id
        FROM department
        WHERE
            name = "公共卫生科"
    ) AS parent_id, t.dept_level, t.is_clinical, t.can_register
FROM (
        SELECT
            "公共卫生科" AS name, 2 AS dept_level, 0 AS is_clinical, 0 AS can_register
    ) AS t;
-- 添加检查项目
INSERT INTO
    examination_item (name, price)
VALUES ("X光胸部正位片", 80.00),
    ("CT头部平扫", 360.00),
    ("CT腹部增强", 720.00),
    ("MRI头部平扫", 680.00),
    ("MRI腰椎平扫", 750.00),
    ("B超腹部常规", 120.00),
    ("B超妇科", 130.00),
    ("B超心脏彩超", 260.00),
    ("B超甲状腺", 110.00),
    ("B超泌尿系", 100.00),
    ("血常规五分类", 35.00),
    ("尿常规", 25.00),
    ("大便常规", 18.00),
    ("肝功能全套", 120.00),
    ("肾功能全套", 90.00),
    ("血糖", 10.00),
    ("血脂全套", 110.00),
    ("乙肝两对半定量", 85.00),
    ("甲胎蛋白(AFP)", 60.00),
    ("癌胚抗原(CEA)", 60.00),
    ("凝血功能四项", 95.00),
    ("电解质六项", 45.00),
    ("心电图常规12导联", 30.00),
    ("动态心电图(Holter)", 280.00),
    ("动态血压监测", 260.00),
    ("肺功能检查", 180.00),
    ("脑电图", 220.00),
    ("肌电图", 300.00),
    ("胃镜普通", 260.00),
    ("无痛胃镜", 600.00),
    ("肠镜普通", 320.00),
    ("无痛肠镜", 700.00),
    ("电子支气管镜", 580.00),
    ("骨密度检测", 150.00),
    ("眼底照相", 90.00),
    ("听力测试(纯音)", 110.00),
    ("糖耐量试验", 80.00),
    ("HbA1c糖化血红蛋白", 70.00),
    ("C反应蛋白(CRP)", 35.00),
    ("核酸检测(通用)", 65.00);