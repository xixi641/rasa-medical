from typing import Optional
import datetime
import decimal

from sqlalchemy import BigInteger, DECIMAL, Date, DateTime, ForeignKeyConstraint, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = 'doctor'
    __table_args__ = {'comment': '医生信息表'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='医生id')
    name: Mapped[Optional[str]] = mapped_column(String(50), comment='医生名称')
    title: Mapped[Optional[str]] = mapped_column(String(20), comment='职称')
    phone: Mapped[Optional[str]] = mapped_column(String(20), comment='医生电话')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    emr: Mapped[list['Emr']] = relationship('Emr', back_populates='doctor')
    doctor_department: Mapped[list['DoctorDepartment']] = relationship('DoctorDepartment', back_populates='doctor')
    doctor_schedule: Mapped[list['DoctorSchedule']] = relationship('DoctorSchedule', back_populates='doctor')
    inpatient_booking: Mapped[list['InpatientBooking']] = relationship('InpatientBooking', back_populates='doctor')
    inpatient_record: Mapped[list['InpatientRecord']] = relationship('InpatientRecord', back_populates='doctor')


class ExaminationItem(Base):
    __tablename__ = 'examination_item'
    __table_args__ = {'comment': '检查项目字典'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='检查项目序号')
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment='检查项目名称')
    price: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(8, 2), comment='价格')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    examination_booking: Mapped[list['ExaminationBooking']] = relationship('ExaminationBooking', back_populates='examination_item')
    examination_report: Mapped[list['ExaminationReport']] = relationship('ExaminationReport', back_populates='examination_item')


class Patient(Base):
    __tablename__ = 'patient'
    __table_args__ = {'comment': '患者信息表'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='患者id')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    phone: Mapped[str] = mapped_column(String(20), nullable=False, comment='患者电话')
    gender: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'0'"), comment='性别(未知 男 女)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    emr: Mapped[list['Emr']] = relationship('Emr', back_populates='patient')
    examination_booking: Mapped[list['ExaminationBooking']] = relationship('ExaminationBooking', back_populates='patient')
    examination_report: Mapped[list['ExaminationReport']] = relationship('ExaminationReport', back_populates='patient')
    feedback: Mapped[list['Feedback']] = relationship('Feedback', back_populates='patient')
    inpatient_booking: Mapped[list['InpatientBooking']] = relationship('InpatientBooking', back_populates='patient')
    inpatient_record: Mapped[list['InpatientRecord']] = relationship('InpatientRecord', back_populates='patient')
    appointment: Mapped[list['Appointment']] = relationship('Appointment', back_populates='patient')


class ShiftItem(Base):
    __tablename__ = 'shift_item'
    __table_args__ = {'comment': '科室值班类型表'}

    name: Mapped[str] = mapped_column(String(20), primary_key=True, comment='班次类型名称')
    schedule: Mapped[dict] = mapped_column(JSON, nullable=False, comment='班次安排')
    description: Mapped[Optional[str]] = mapped_column(String(255), comment='班次描述')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    department: Mapped[list['Department']] = relationship('Department', back_populates='shift_item')


class Department(Base):
    __tablename__ = 'department'
    __table_args__ = (
        ForeignKeyConstraint(['parent_id'], ['department.id'], name='department_ibfk_1'),
        ForeignKeyConstraint(['shift_type_name'], ['shift_item.name'], name='department_ibfk_2'),
        Index('parent_id', 'parent_id'),
        Index('shift_type_name', 'shift_type_name'),
        {'comment': '科室信息表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='科室id')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='上级科室id(用于二级科室指向一级科室)')
    dept_level: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'1'"), comment='科室级别(1=一级科室，2=级科室)')
    is_clinical: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'1'"), comment='是否为临床科室(0=否，1=是)')
    can_register: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'1'"), comment='是否可用于患者挂号(0=否，1=是)')
    shift_type_name: Mapped[Optional[str]] = mapped_column(String(20), comment='值班类型名称')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    parent: Mapped[Optional['Department']] = relationship('Department', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[list['Department']] = relationship('Department', remote_side=[parent_id], back_populates='parent')
    shift_item: Mapped[Optional['ShiftItem']] = relationship('ShiftItem', back_populates='department')
    doctor_department: Mapped[list['DoctorDepartment']] = relationship('DoctorDepartment', back_populates='dept')
    doctor_schedule: Mapped[list['DoctorSchedule']] = relationship('DoctorSchedule', back_populates='dept')
    inpatient_booking: Mapped[list['InpatientBooking']] = relationship('InpatientBooking', back_populates='dept')
    inpatient_record: Mapped[list['InpatientRecord']] = relationship('InpatientRecord', back_populates='dept')


class Emr(Base):
    __tablename__ = 'emr'
    __table_args__ = (
        ForeignKeyConstraint(['doctor_id'], ['doctor.id'], name='emr_ibfk_2'),
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='emr_ibfk_1'),
        Index('case_id', 'case_id', 'emr_type', 'version', unique=True),
        Index('doctor_id', 'doctor_id'),
        Index('patient_id', 'patient_id'),
        {'comment': '电子病历表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='病历id')
    patient_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='患者id')
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, comment='治疗流程编号')
    visit_type: Mapped[str] = mapped_column(String(20), nullable=False, comment='就诊类型(门诊、住院、急诊)')
    emr_type: Mapped[str] = mapped_column(String(20), nullable=False, comment='病历类型(首诊病历、随访病历、出院小结)')
    content: Mapped[Optional[dict]] = mapped_column(JSON, comment='结构化病历JSON，可存主诉/现病史/诊断/处方')
    signature: Mapped[Optional[dict]] = mapped_column(JSON, comment='电子签名')
    version: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text("'1'"), comment='版本号(用于追踪病历修改历史)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    doctor: Mapped['Doctor'] = relationship('Doctor', back_populates='emr')
    patient: Mapped['Patient'] = relationship('Patient', back_populates='emr')


class ExaminationBooking(Base):
    __tablename__ = 'examination_booking'
    __table_args__ = (
        ForeignKeyConstraint(['examination_item_id'], ['examination_item.id'], name='examination_booking_ibfk_2'),
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='examination_booking_ibfk_1'),
        Index('examination_item_id', 'examination_item_id'),
        Index('patient_id', 'patient_id'),
        {'comment': '检查预约表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='检查预约id')
    patient_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='患者id')
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    examination_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='检查项目id')
    examination_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment='预约检查日期')
    start_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='开始时间')
    end_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='结束时间')
    examination_item_name: Mapped[Optional[str]] = mapped_column(String(100), comment='检查项目名称')
    queue_no: Mapped[Optional[int]] = mapped_column(Integer, comment='当天序号')
    status: Mapped[Optional[int]] = mapped_column(TINYINT, comment='预约状态(1=已预约 2=已检查 3=已取消)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    examination_item: Mapped['ExaminationItem'] = relationship('ExaminationItem', back_populates='examination_booking')
    patient: Mapped['Patient'] = relationship('Patient', back_populates='examination_booking')


class ExaminationReport(Base):
    __tablename__ = 'examination_report'
    __table_args__ = (
        ForeignKeyConstraint(['examination_item_id'], ['examination_item.id'], name='examination_report_ibfk_2'),
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='examination_report_ibfk_1'),
        Index('examination_item_id', 'examination_item_id'),
        Index('patient_id', 'patient_id'),
        {'comment': '检查报告表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='检查报告id')
    patient_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='患者id')
    patient_name: Mapped[Optional[str]] = mapped_column(String(50), comment='患者名称')
    examination_item_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='检查项目id')
    examination_item_name: Mapped[Optional[str]] = mapped_column(String(100), comment='检查项目名称')
    examination_date: Mapped[Optional[datetime.date]] = mapped_column(Date, comment='检查日期')
    examination_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='检查时间')
    pdf_url: Mapped[Optional[str]] = mapped_column(String(255), comment='检查报告pdf链接')
    summary: Mapped[Optional[str]] = mapped_column(Text, comment='总结')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    examination_item: Mapped[Optional['ExaminationItem']] = relationship('ExaminationItem', back_populates='examination_report')
    patient: Mapped[Optional['Patient']] = relationship('Patient', back_populates='examination_report')


class Feedback(Base):
    __tablename__ = 'feedback'
    __table_args__ = (
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='feedback_ibfk_1'),
        Index('patient_id', 'patient_id'),
        {'comment': '信息反馈表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='反馈信息id')
    patient_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='反馈患者id')
    type: Mapped[Optional[str]] = mapped_column(String(20), comment='建议类型(建议 系统故障)')
    title: Mapped[Optional[str]] = mapped_column(String(255), comment='反馈标题')
    content: Mapped[Optional[str]] = mapped_column(Text, comment='反馈内容')
    pic_urls: Mapped[Optional[dict]] = mapped_column(JSON, comment='反馈图片链接JSON数组')
    status: Mapped[Optional[int]] = mapped_column(TINYINT, comment='处理状态(1=待处理 2=已处理)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    patient: Mapped[Optional['Patient']] = relationship('Patient', back_populates='feedback')


class DoctorDepartment(Base):
    __tablename__ = 'doctor_department'
    __table_args__ = (
        ForeignKeyConstraint(['dept_id'], ['department.id'], name='doctor_department_ibfk_2'),
        ForeignKeyConstraint(['doctor_id'], ['doctor.id'], name='doctor_department_ibfk_1'),
        Index('dept_id', 'dept_id'),
        Index('doctor_id', 'doctor_id'),
        {'comment': '医生科室关联表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='科室id')
    dept_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    is_primary: Mapped[int] = mapped_column(TINYINT, nullable=False, comment='是否为主属科室(0=否，1=是)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    dept: Mapped['Department'] = relationship('Department', back_populates='doctor_department')
    doctor: Mapped['Doctor'] = relationship('Doctor', back_populates='doctor_department')


class DoctorSchedule(Base):
    __tablename__ = 'doctor_schedule'
    __table_args__ = (
        ForeignKeyConstraint(['dept_id'], ['department.id'], name='doctor_schedule_ibfk_2'),
        ForeignKeyConstraint(['doctor_id'], ['doctor.id'], name='doctor_schedule_ibfk_1'),
        Index('dept_id', 'dept_id'),
        Index('doctor_id', 'doctor_id'),
        {'comment': '医生排班信息表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='排班信息id')
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='科室id')
    dept_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    schedule_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment='排班日期')
    start_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='开始时间')
    end_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='结束时间')
    shift_no: Mapped[Optional[int]] = mapped_column(BigInteger, comment='班次号')
    appointment_limit: Mapped[Optional[int]] = mapped_column(Integer, comment='挂号数上限')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    dept: Mapped['Department'] = relationship('Department', back_populates='doctor_schedule')
    doctor: Mapped['Doctor'] = relationship('Doctor', back_populates='doctor_schedule')
    appointment: Mapped[list['Appointment']] = relationship('Appointment', back_populates='schedule')


class InpatientBooking(Base):
    __tablename__ = 'inpatient_booking'
    __table_args__ = (
        ForeignKeyConstraint(['dept_id'], ['department.id'], name='inpatient_booking_ibfk_3'),
        ForeignKeyConstraint(['doctor_id'], ['doctor.id'], name='inpatient_booking_ibfk_2'),
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='inpatient_booking_ibfk_1'),
        Index('dept_id', 'dept_id'),
        Index('doctor_id', 'doctor_id'),
        Index('patient_id', 'patient_id'),
        {'comment': '住院预约表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='住院预约id')
    patient_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='患者id')
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='科室id')
    dept_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    expected_date: Mapped[Optional[datetime.date]] = mapped_column(Date, comment='入院日期')
    bed_type: Mapped[Optional[int]] = mapped_column(TINYINT, comment='病床类型(1=普通 2=单人间 3=ICU)')
    status: Mapped[Optional[int]] = mapped_column(TINYINT, comment='预约状态(1=排队中 2=已预约 3=已入院 4=已取消)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    dept: Mapped['Department'] = relationship('Department', back_populates='inpatient_booking')
    doctor: Mapped['Doctor'] = relationship('Doctor', back_populates='inpatient_booking')
    patient: Mapped['Patient'] = relationship('Patient', back_populates='inpatient_booking')


class InpatientRecord(Base):
    __tablename__ = 'inpatient_record'
    __table_args__ = (
        ForeignKeyConstraint(['dept_id'], ['department.id'], name='inpatient_record_ibfk_2'),
        ForeignKeyConstraint(['doctor_id'], ['doctor.id'], name='inpatient_record_ibfk_3'),
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='inpatient_record_ibfk_1'),
        Index('dept_id', 'dept_id'),
        Index('doctor_id', 'doctor_id'),
        Index('patient_id', 'patient_id'),
        {'comment': '住院记录表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='住院记录id')
    patient_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='患者id')
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='科室id')
    dept_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    bed_type: Mapped[Optional[int]] = mapped_column(TINYINT, comment='病床类型(1=普通 2=单人间 3=ICU)')
    bed_no: Mapped[Optional[int]] = mapped_column(BigInteger, comment='床位号')
    admission_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='入院时间')
    discharge_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='出院时间')
    status: Mapped[Optional[int]] = mapped_column(TINYINT, comment='住院状态(1=在院 2=已出院)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    dept: Mapped['Department'] = relationship('Department', back_populates='inpatient_record')
    doctor: Mapped['Doctor'] = relationship('Doctor', back_populates='inpatient_record')
    patient: Mapped['Patient'] = relationship('Patient', back_populates='inpatient_record')


class Appointment(Base):
    __tablename__ = 'appointment'
    __table_args__ = (
        ForeignKeyConstraint(['patient_id'], ['patient.id'], name='appointment_ibfk_1'),
        ForeignKeyConstraint(['schedule_id'], ['doctor_schedule.id'], name='appointment_ibfk_2'),
        Index('patient_id', 'patient_id'),
        Index('schedule_id', 'schedule_id'),
        {'comment': '挂号表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='挂号id')
    patient_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='患者id')
    patient_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='患者名称')
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='科室id')
    dept_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='科室名称')
    doctor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='医生id')
    doctor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='医生名称')
    shift_no: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='班次号')
    visit_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment='预约日期')
    schedule_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='排班id')
    start_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='开始时间')
    end_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='结束时间')
    queue_no: Mapped[Optional[int]] = mapped_column(Integer, comment='当天序号')
    status: Mapped[Optional[int]] = mapped_column(TINYINT, comment='预约状态(1=已预约 2=已取号 3=已取消)')
    create_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text("'0'"), comment='是否删除(0=未删除，1=已删除)')

    patient: Mapped['Patient'] = relationship('Patient', back_populates='appointment')
    schedule: Mapped['DoctorSchedule'] = relationship('DoctorSchedule', back_populates='appointment')

