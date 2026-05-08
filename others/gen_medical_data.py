# pip install pymysql sqlalchemy sqlacodegen faker neo4j numpy tqdm cryptography
import os
import random
import datetime
import subprocess
from faker import Faker
from sqlalchemy import select
from neo4j import GraphDatabase
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from collections import deque, defaultdict

tag = {
    "error": "\033[1;31m[ERROR]\033[0m",
    "success": "\033[1;32m[SUCCESS]\033[0m",
    "processing": "\033[1;34m[PROCESSING]\033[0m",
}

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "medical",
    "charset": "utf8mb4",
}
mysql_url = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8"

NEO4J_URL = "neo4j://127.0.0.1"
NEO4J_AUTH = ("neo4j", "12345678")

fake = Faker("zh_CN")


def create_database(mysql_config: dict, sql_file_path: str, output_paths: list[str]):
    """
    - 创建数据库
    - 使用 sql 文件导入表
    - 将表映射为 Python 类
    """

    mysql_cmd_prefix = [
        "mysql.exe",
        f"-h{mysql_config['host']}",
        f"-P{mysql_config['port']}",
        f"-u{mysql_config['user']}",
        f"-p{mysql_config['password']}",
        f"--default-character-set={mysql_config['charset']}",
    ]

    # 创建数据库
    print(f"{tag['processing']} 创建 {mysql_config['database']}")
    cmd = mysql_cmd_prefix + [
        "-e",
        f"create database if not exists {mysql_config['database']};",
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        error_msg = result.stderr.splitlines()[1:][0] if result.stderr.splitlines()[1:] else result.stderr
        print(f"{tag['error']} {error_msg}")
        return
    print(f"{tag['success']} {mysql_config['database']} 创建成功")

    # 导入数据
    print(f"{tag['processing']} 导入表单数据")
    with open(sql_file_path, "r", encoding='utf-8') as sql_file:
        result = subprocess.run(
            mysql_cmd_prefix + [mysql_config["database"]],
            stdin=sql_file,
            stderr=subprocess.PIPE,
            text=True,
        )
    if result.returncode != 0:
        error_msg = result.stderr.splitlines()[1:][0] if result.stderr.splitlines()[1:] else result.stderr
        print(f"{tag['error']} {error_msg}")
        return
    print(f"{tag['success']} 表单数据导入成功")

    # 生成数据库表映射
    print(f"{tag['processing']} 生成数据库表映射")
    cmd = ["python", "-m", "sqlacodegen", mysql_url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        print(f"{tag['error']} {result.stderr}")
        return
    for output_path in output_paths:
        with open(output_path, "w", encoding="utf-8") as ofile:
            ofile.write(result.stdout)
        print(f"{tag['success']} 数据库表映射已保存到 {output_path}")


sql_file_path = os.path.join(os.path.dirname(__file__), "medical.sql")
output_paths = [os.path.join(os.path.dirname(__file__), "orm.py")]
for i in output_paths:
    if not os.path.exists(i):
        create_database(MYSQL_CONFIG, sql_file_path, output_paths)
        break

import orm
from utils import ScheduleState, gen_emr_content, gen_emr_signature



def time_elapses(this_time: datetime.datetime | None, delta_second: int):
    """生成在指定时间段内，且小于当前时间的新时间"""
    if this_time is None:
        return None
    interval_second = int((datetime.datetime.now() - this_time).total_seconds())
    max_delta_second = min(delta_second, interval_second)
    delta_second = random.randint(0, max_delta_second)
    return this_time + datetime.timedelta(seconds=delta_second)


def gen_patient(nums=500) -> list[orm.Patient]:
    """生成患者信息"""
    patients = [
        orm.Patient(
            name=fake.name(),
            phone=fake.phone_number(),
            gender=random.choice(["未知", "男", "女"]),
        )
        for _ in range(nums)
    ]
    print(f"{tag['success']} 生成 {len(patients)} 条患者信息")
    session.add_all(patients)
    return patients


def gen_doctor(nums=300) -> list[orm.Doctor]:
    """生成医生信息"""
    doctors = [
        orm.Doctor(
            name=fake.name(),
            title=random.choice(["主任医师", "副主任医师", "主治医师", "医师"]),
            phone=fake.phone_number(),
        )
        for _ in range(nums)
    ]
    print(f"{tag['success']} 生成 {len(doctors)} 条医生信息")
    session.add_all(doctors)
    return doctors


def gen_doctor_dept_rel(
    doctors: list[orm.Doctor], departments: list[orm.Department]
) -> list[orm.DoctorDepartment]:
    """生成医生科室关系"""
    doctor_dept_rels = []
    # 将所有医生放入队列
    candidate_doctors = deque(doctors)
    # 找出没有子类的科室
    candidate_depts = [d for d in departments if not d.parent_reverse]
    # 维护医生→主属科室映射
    doctor_dept_map: dict[int, orm.Department] = {}

    # 阶段一：为每个科室分配医生
    for dept in candidate_depts:
        for _ in range(4):
            if not candidate_doctors:
                print(f"{tag['error']} 没有足够的医生可供 {dept.name} 分配")
                break
            doctor = candidate_doctors.pop()
            doctor_dept_rels.append(
                orm.DoctorDepartment(
                    doctor=doctor,
                    dept=dept,
                    doctor_name=doctor.name,
                    dept_name=dept.name,
                    is_primary=1,
                )
            )
            doctor_dept_map[doctor.id] = dept

    # 阶段二：剩余医生随机分配到科室
    while candidate_doctors:
        doctor = candidate_doctors.pop()
        dept = random.choice(candidate_depts)
        doctor_dept_rels.append(
            orm.DoctorDepartment(
                doctor=doctor,
                dept=dept,
                doctor_name=doctor.name,
                dept_name=dept.name,
                is_primary=1,
            )
        )
        doctor_dept_map[doctor.id] = dept

    # 阶段三：为部分医生分配第二科室
    candidate_doctors = random.sample(doctors, int(0.1 * len(doctors)))
    for doctor in candidate_doctors:
        # 过滤掉该医生的主属科室
        second_depts = set(candidate_depts) - set([doctor_dept_map[doctor.id]])
        # 优先急诊科
        emergency_depts = [d for d in second_depts if d.parent.name == "急诊科"]
        dept = random.choice(list(second_depts) + emergency_depts * 20)
        doctor_dept_rels.append(
            orm.DoctorDepartment(
                doctor=doctor,
                dept=dept,
                doctor_name=doctor.name,
                dept_name=dept.name,
                is_primary=0,
            )
        )

    print(f"{tag['success']} 生成 {len(doctor_dept_rels)} 条医生科室关系")
    session.add_all(doctor_dept_rels)
    return doctor_dept_rels


def gen_one_week_schedule(
    days: list[datetime.date],
    doctor_id_map: dict[int, orm.Doctor],
    dept_id_map: dict[int, orm.Department],
    dept_doctors: dict[int, list[orm.Doctor]],
    max_iter: int,
) -> list[orm.DoctorSchedule]:
    """生成1周的门诊排班"""
    one_week_schedule: list[orm.DoctorSchedule] = []
    # 不同职称挂号上限
    REGISTER_LIMIT = {"主任医师": 20, "副主任医师": 25, "主治医师": 30, "医师": 40}
    # 不同时段值班人数
    REQ_PER_SHIFT = [3, 2, 2]
    # with session.no_autoflush:
    schedule = ScheduleState(
        days, dept_id_map.values(), dept_doctors, REQ_PER_SHIFT
    ).simulated_annealing(max_iter)
    for dept_id, all_shifts in schedule.items():
        for day, day_shifts in all_shifts.items():
            for shift, doctor_set in day_shifts.items():
                dept_day_s_time = dept_id_map[dept_id].schedule[shift]
                start_time = dept_day_s_time["start"]
                end_time = dept_day_s_time["end"]
                start_time = datetime.datetime.strptime(start_time, "%H:%M").time()
                end_time = datetime.datetime.strptime(end_time, "%H:%M").time()
                start_datetime = datetime.datetime.combine(day, start_time)
                end_datetiem = datetime.datetime.combine(day, end_time)
                if end_time < start_time:
                    end_datetiem += datetime.timedelta(days=1)
                for doctor_id in doctor_set:
                    one_week_schedule.append(
                        orm.DoctorSchedule(
                            doctor=doctor_id_map[doctor_id],
                            doctor_name=doctor_id_map[doctor_id].name,
                            dept=dept_id_map[dept_id],
                            dept_name=dept_id_map[dept_id].name,
                            schedule_date=day,
                            start_datetime=start_datetime,
                            end_datetime=end_datetiem,
                            shift_no=shift,
                            appointment_limit=REGISTER_LIMIT[
                                doctor_id_map[doctor_id].title
                            ],
                        )
                    )
    return one_week_schedule


def gen_doctor_schedule(
    doctors: list[orm.Doctor],
    departments: list[orm.Department],
    doctor_dept_rels: list[orm.DoctorDepartment],
    max_iter: int = 10000,
) -> list[orm.DoctorSchedule]:
    """生成医生排班信息"""
    doctor_schedules: list[orm.DoctorSchedule] = []

    # 医生id→医生
    doctor_id_map: dict[int, orm.Doctor] = {d.id: d for d in doctors}
    # 不同职称班次数
    SHIFT_LIMITS = {"主任医师": 4, "副主任医师": 6, "主治医师": 10, "医师": 12}
    # 添加医生班次数信息
    for doctor in doctors:
        doctor.shift_limit = SHIFT_LIMITS[doctor.title]

    # 科室→医生
    dept_doctors: dict[int, list[orm.Doctor]] = defaultdict(list)
    for doctor_dept_rel in doctor_dept_rels:
        # 添加医生主属科室信息
        if doctor_dept_rel.is_primary:
            doctor_dept_rel.doctor.primary_dept_id = doctor_dept_rel.dept.id
        dept_doctors[doctor_dept_rel.dept.id].append(doctor_dept_rel.doctor)

    # 需要门诊排班的科室
    depts = [
        dept
        for dept in departments
        if dept.is_deleted == 0 and dept.can_register == 1 and not dept.parent_reverse
    ]
    # 科室id→科室
    dept_id_map: dict[int, orm.Department] = {d.id: d for d in depts}
    # 科室添加排班时间表
    for dept in depts:
        if dept.shift_item:
            continue
        if not dept.parent:
            print(f"{dept.name} 科室没有上级科室")
            continue
        if not dept.parent.shift_item:
            print(f"{dept.name} 科室的上级科室没有排班时间表")
            continue
        dept.schedule = dept.parent.shift_item.schedule

    # 生成门诊排班
    today = datetime.date.today()
    this_moday = today - datetime.timedelta(days=today.weekday())
    for days in [[this_moday + datetime.timedelta(days=i) for i in range(7)]]:
        # 生成1周的门诊排班
        one_week_doctor_schedule = gen_one_week_schedule(
            days, doctor_id_map, dept_id_map, dept_doctors, max_iter
        )
        doctor_schedules.extend(one_week_doctor_schedule)
    print(f"{tag['success']} 生成 {len(doctor_schedules)} 条医生排班信息")
    session.add_all(doctor_schedules)
    session.flush()
    return doctor_schedules


def gen_appointment(
    patients: list[orm.Patient], doctor_schedules: list[orm.DoctorSchedule], nums=400
) -> list[orm.Appointment]:
    """生成挂号信息"""
    appointments: list[orm.Appointment] = []
    # 排班id→排班
    schedule_id_map: dict[int, orm.DoctorSchedule] = {s.id: s for s in doctor_schedules}
    # 今天日期与本周一日期
    today = datetime.date.today()
    this_moday = today - datetime.timedelta(days=today.weekday())
    # 候选患者
    candidate_patients = random.choices(patients, k=nums)
    # 统计周一到今天每天每个科室每个班次每个排班的可挂号人数
    day_dept_shift_doctor: dict[datetime.date, dict[int, dict[int, dict[int, int]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    )
    for schedule in doctor_schedules:
        if (
            schedule.start_datetime.date() > today
            or schedule.start_datetime.date() < this_moday
        ):
            continue
        day_dept_shift_doctor[schedule.start_datetime.date()][schedule.dept_id][
            schedule.shift_no
        ][schedule.id] += schedule.appointment_limit
    # 统计每天每科室挂号序号
    day_dept_appointment_no: dict[datetime.date, dict[int, int]] = defaultdict(
        lambda: defaultdict(lambda: 1)
    )
    # 生成挂号信息
    for patient in candidate_patients:
        if not day_dept_shift_doctor:
            print(f"{tag['error']} 已无号源")
            break
        # 挂号日期
        day = random.choice(list(day_dept_shift_doctor.keys()))
        # 挂号科室
        dept_id = random.choice(list(day_dept_shift_doctor[day].keys()))
        # 挂号班次
        shift_no = random.choice(list(day_dept_shift_doctor[day][dept_id].keys()))
        # 挂号医生
        schedule_id = random.choice(
            list(day_dept_shift_doctor[day][dept_id][shift_no].keys())
        )
        # 挂号时间段
        start_datetime = schedule_id_map[schedule_id].start_datetime
        end_datetime = schedule_id_map[schedule_id].end_datetime
        # 挂号序号
        queue_no = day_dept_appointment_no[day][dept_id]
        day_dept_appointment_no[day][dept_id] += 1
        # 挂号状态
        if day < today:
            status = random.choices([2, 3], weights=[0.9, 0.1], k=1)[0]
        elif schedule_id_map[schedule_id].start_datetime < datetime.datetime.now():
            status = random.choices([1, 2, 3], weights=[0.8, 0.1, 0.1], k=1)[0]
        else:
            status = 1
        # 科室名称
        dept_name = schedule_id_map[schedule_id].dept.name
        # 医生id与名称
        doctor_id = schedule_id_map[schedule_id].doctor_id
        doctor_name = schedule_id_map[schedule_id].doctor.name
        # 创建时间
        day_begin_datetime = datetime.datetime.combine(day, datetime.time())
        delta_seconds = (end_datetime - day_begin_datetime).seconds
        create_time = time_elapses(day_begin_datetime, delta_seconds)
        appointments.append(
            orm.Appointment(
                patient=patient,
                patient_name=patient.name,
                schedule=schedule_id_map[schedule_id],
                dept_id=dept_id,
                dept_name=dept_name,
                doctor_id=doctor_id,
                doctor_name=doctor_name,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                shift_no=shift_no,
                visit_date=day,
                queue_no=queue_no,
                status=status,
                create_time=create_time,
            )
        )
        if status == 3:
            continue
        # 更新可挂号人数
        day_dept_shift_doctor[day][dept_id][shift_no][schedule_id] -= 1
        if day_dept_shift_doctor[day][dept_id][shift_no][schedule_id] == 0:
            del day_dept_shift_doctor[day][dept_id][shift_no][schedule_id]
        if not day_dept_shift_doctor[day][dept_id][shift_no]:
            del day_dept_shift_doctor[day][dept_id][shift_no]
        if not day_dept_shift_doctor[day][dept_id]:
            del day_dept_shift_doctor[day][dept_id]
        if not day_dept_shift_doctor[day]:
            del day_dept_shift_doctor[day]
    print(f"{tag['success']} 生成 {len(appointments)} 条挂号信息")
    session.add_all(appointments)
    return appointments


def gen_emr(appointments: list[orm.Appointment]) -> list[orm.Emr]:
    """生成电子病历"""
    emrs: list[orm.Emr] = []
    for appointment in appointments:
        if appointment.status != 2:
            continue
        # 病历内容
        emr_content = gen_emr_content()
        # 签名
        day_over_datetime = datetime.datetime.combine(
            appointment.start_datetime.date(), datetime.time.max
        )
        delta_seconds = (day_over_datetime - appointment.start_datetime).seconds
        sign_datetime = time_elapses(appointment.start_datetime, delta_seconds)
        signature = gen_emr_signature(emr_content, sign_datetime)
        # 就诊id
        case_id = f"{appointment.patient.id}-{appointment.dept_id}-{sign_datetime.strftime('%Y%m%d%H%M%S')}"
        emrs.append(
            orm.Emr(
                patient=appointment.patient,
                patient_name=appointment.patient_name,
                doctor=appointment.schedule.doctor,
                doctor_name=appointment.schedule.doctor.name,
                case_id=case_id,
                visit_type="门诊",
                emr_type="首诊病历",
                content=emr_content,
                signature=signature,
                create_time=sign_datetime,
            )
        )
    print(f"{tag['success']} 生成 {len(emrs)} 条电子病历")
    session.add_all(emrs)
    return emrs


def gen_examination_booking(
    patients: list[orm.Patient], examination_items: list[orm.ExaminationItem], nums=300
) -> list[orm.ExaminationBooking]:
    """生成检查预约"""
    examination_bookings: list[orm.ExaminationBooking] = []
    today = datetime.date.today()
    this_moday = today - datetime.timedelta(days=today.weekday())
    days = [this_moday + datetime.timedelta(days=i) for i in range(7)]
    book_times = [
        {"start": "08:00", "end": "12:00"},
        {"start": "14:00", "end": "18:00"},
    ]
    candidate_patients = random.choices(patients, k=nums)
    # 统计每天每项检查序号
    day_examination_booking_no: dict[datetime.date, dict[int, int]] = defaultdict(
        lambda: defaultdict(lambda: 1)
    )
    for patient in candidate_patients:
        examination_date = random.choice(days)
        book_time = random.choice(book_times)
        start_time = datetime.datetime.strptime(book_time["start"], "%H:%M").time()
        end_time = datetime.datetime.strptime(book_time["end"], "%H:%M").time()
        start_datetime = datetime.datetime.combine(examination_date, start_time)
        end_datetime = datetime.datetime.combine(examination_date, end_time)
        # 检查日期早于今天
        if examination_date < today:
            status = random.choices([2, 3], weights=[0.9, 0.1], k=1)[0]
        # 检查日期等于今天，但开始时间早于当前时间
        elif examination_date == today and (
            datetime.datetime.strptime(book_time["start"], "%H:%M").time()
            < datetime.datetime.now().time()
        ):
            status = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]
        # 检查时间在当前时间之后
        else:
            status = random.choices([1, 3], weights=[0.9, 0.1], k=1)[0]
        examination_item = random.choice(examination_items)
        queue_no = day_examination_booking_no[examination_date][examination_item.id]
        day_examination_booking_no[examination_date][examination_item.id] += 1
        examination_bookings.append(
            orm.ExaminationBooking(
                patient=patient,
                patient_name=patient.name,
                examination_item=examination_item,
                examination_item_name=examination_item.name,
                examination_date=examination_date,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                queue_no=queue_no,
                status=status,
            )
        )
    print(f"{tag['success']} 生成 {len(examination_bookings)} 条检查预约")
    session.add_all(examination_bookings)
    session.flush()
    return examination_bookings


def gen_examination_report(
    examination_bookings: list[orm.ExaminationBooking],
) -> list[orm.ExaminationReport]:
    """生成检查报告"""
    examination_reports: list[orm.ExaminationReport] = []
    for examination_booking in examination_bookings:
        if examination_booking.status != 2:
            continue
        this_time = datetime.datetime.now()
        start_datetime = examination_booking.start_datetime
        end_datetime = examination_booking.end_datetime
        # 当前时间在检查时间段内
        if start_datetime < this_time and this_time < end_datetime:
            delta_seconds = (this_time - start_datetime).seconds
            examination_time = time_elapses(start_datetime, delta_seconds)
        # 当前时间在检查时间段外
        else:
            delta_seconds = (end_datetime - start_datetime).seconds
            examination_time = time_elapses(start_datetime, delta_seconds)
        pdf_url = f"http://{examination_booking.examination_item.id}/{examination_booking.examination_date.strftime('%Y%m%d')}/{examination_booking.id}.pdf"
        examination_reports.append(
            orm.ExaminationReport(
                patient=examination_booking.patient,
                patient_name=examination_booking.patient_name,
                examination_item=examination_booking.examination_item,
                examination_item_name=examination_booking.examination_item_name,
                examination_date=examination_booking.examination_date,
                examination_time=examination_time,
                summary="未见异常",
                pdf_url=pdf_url,
            )
        )
    print(f"{tag['success']} 生成 {len(examination_reports)} 条检查报告")
    session.add_all(examination_reports)
    return examination_reports


def gen_inpatient_booking(appointments: list[orm.Appointment]):
    """生成住院预约"""
    inpatient_bookings: list[orm.InpatientBooking] = []
    for appointment in appointments:
        if appointment.status != 2 or random.randint(0, 1):
            continue
        status = random.choices([1, 2, 3, 4], weights=[0.3, 0.3, 0.3, 0.1], k=1)[0]
        bed_type = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1], k=1)[0]
        # 创建时间
        day_over_datetime = datetime.datetime.combine(
            appointment.create_time.date(), datetime.time.max
        )
        delta_seconds = (day_over_datetime - appointment.create_time).seconds
        create_time = time_elapses(appointment.create_time, delta_seconds)
        # 入院时间
        if status in [2, 3]:
            expected_date = appointment.visit_date
        elif status == 1:
            expected_date = None
        elif status == 4:
            expected_date = random.choice([None, appointment.visit_date])
        inpatient_bookings.append(
            orm.InpatientBooking(
                patient=appointment.patient,
                patient_name=appointment.patient_name,
                dept=appointment.schedule.dept,
                dept_name=appointment.dept_name,
                doctor=appointment.schedule.doctor,
                doctor_name=appointment.doctor_name,
                expected_date=expected_date,
                bed_type=bed_type,
                status=status,
                create_time=create_time,
            )
        )
    print(f"{tag['success']} 生成 {len(inpatient_bookings)} 条住院预约")
    session.add_all(inpatient_bookings)
    return inpatient_bookings


def gen_inpatient_record(inpatient_bookings: list[orm.InpatientBooking]):
    """生成住院记录"""
    inpatient_records: list[orm.InpatientRecord] = []
    for inpatient_booking in inpatient_bookings:
        if inpatient_booking.status != 3:
            continue
        # 床位
        bed_no = 1
        if inpatient_booking.bed_type == 1:
            bed_no = random.randint(1, 6)
        # 入院时间
        expected_date = datetime.datetime.combine(
            inpatient_booking.expected_date, datetime.time()
        )
        this_time = max(expected_date, inpatient_booking.create_time)
        delta_seconds = (
            datetime.datetime.combine(
                inpatient_booking.expected_date + datetime.timedelta(days=1),
                datetime.time(),
            )
            - this_time
        ).seconds
        admission_time = time_elapses(this_time, delta_seconds)
        # 住院状态
        status = random.choices([1, 2], weights=[0.9, 0.1], k=1)[0]
        # 出院时间
        discharge_time = None
        if status == 2:
            delta_seconds = (datetime.datetime.now() - admission_time).seconds
            discharge_time = time_elapses(admission_time, delta_seconds)
        inpatient_records.append(
            orm.InpatientRecord(
                patient=inpatient_booking.patient,
                patient_name=inpatient_booking.patient_name,
                dept=inpatient_booking.dept,
                dept_name=inpatient_booking.dept_name,
                doctor=inpatient_booking.doctor,
                doctor_name=inpatient_booking.doctor_name,
                bed_type=inpatient_booking.bed_type,
                bed_no=bed_no,
                admission_time=admission_time,
                discharge_time=discharge_time,
                status=status,
            )
        )
    print(f"{tag['success']} 生成 {len(inpatient_records)} 条住院记录")
    session.add_all(inpatient_records)
    return inpatient_records


def import2neo4j(
    departments: list[orm.Department], examination_items: list[orm.ExaminationItem]
):
    """将MySQL中的科室和检查项目导入Neo4j"""
    department_nodes = [{"name": d.name, "can_use": True} for d in departments]
    examination_item_nodes = [
        {"name": item.name, "can_use": True} for item in examination_items
    ]
    with GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH) as driver:
        driver.execute_query(
            "UNWIND $rows AS row "
            "MERGE (n:Department {name: row.name}) "
            "SET n.can_use = row.can_use",
            {"rows": department_nodes},
        )
        driver.execute_query(
            "UNWIND $rows AS row "
            "MERGE (n:Check {name: row.name}) "
            "SET n.can_use = row.can_use",
            {"rows": examination_item_nodes},
        )
    print(f"{tag['success']} 科室与检查项目数据导入Neo4j")


if __name__ == "__main__":
    engine = create_engine(mysql_url)
    with Session(engine) as session:
        departments = session.scalars(select(orm.Department)).all()
        examination_items = session.scalars(select(orm.ExaminationItem)).all()
        patients = gen_patient()
        doctors = gen_doctor()
        doctor_dept_rels = gen_doctor_dept_rel(doctors, departments)
        doctor_schedules = gen_doctor_schedule(
            doctors, departments, doctor_dept_rels, 10000
        )
        appointments = gen_appointment(patients, doctor_schedules)
        emrs = gen_emr(appointments)
        examination_bookings = gen_examination_booking(patients, examination_items)
        examination_reports = gen_examination_report(examination_bookings)
        inpatient_bookings = gen_inpatient_booking(appointments)
        inpatient_records = gen_inpatient_record(inpatient_bookings)
        session.commit()

        import2neo4j(departments, examination_items)
