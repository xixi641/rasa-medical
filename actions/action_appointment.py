from typing import Any, Text, Dict, List

from rasa_sdk.events import SlotSet, ActionExecutionRejected
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

import datetime
from sqlalchemy import select, func
from .db import mysql_session
from .orm import Appointment, DoctorSchedule, Department, Patient


class AskDepartmentLevel1Id(Action):
    """获取一级科室id"""

    def name(self) -> Text:
        return "action_ask_department_level1_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        with mysql_session() as session:
            # 查询可挂号的一级科室
            department_level1s = session.execute(
                select(Department.id, Department.name)
                .where(Department.can_register == 1)
                .where(Department.dept_level == 1)
                .where(Department.is_deleted == 0)
            ).all()

        if not department_level1s:
            return [
                SlotSet("department_level1_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        for department in department_level1s:
            buttons.append(
                {
                    "title": f"{department.name}",
                    "payload": f"/SetSlots(department_level1_id={department.id})",
                }
            )
        dispatcher.utter_message(text="请选择一级科室：", buttons=buttons)


class AskDepartmentLevel2Id(Action):
    """获取二级科室id"""

    def name(self) -> Text:
        return "action_ask_department_level2_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        department_level1_id = tracker.get_slot("department_level1_id")
        now_datetime = datetime.datetime.now()
        with mysql_session() as session:
            # 查询可挂号的二级科室
            department_level2s = session.execute(
                select(DoctorSchedule.dept_id, DoctorSchedule.dept_name)
                .where(DoctorSchedule.schedule_date == now_datetime.date())
                .where(DoctorSchedule.end_datetime >= now_datetime)
                .where(DoctorSchedule.dept.has(dept_level=2))
                .where(DoctorSchedule.dept.has(parent_id=department_level1_id))
                .where(DoctorSchedule.is_deleted == 0)
                .group_by(DoctorSchedule.dept_id, DoctorSchedule.dept_name)
            ).all()

        if not department_level2s:
            return [
                SlotSet("department_level2_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        for department in department_level2s:
            buttons.append(
                {
                    "title": f"{department.dept_name}",
                    "payload": f"/SetSlots(department_level2_id={department.dept_id})",
                }
            )
        dispatcher.utter_message(text="请选择二级科室：", buttons=buttons)


class AskAppointmentShiftId(Action):
    """获取班次序号"""

    def name(self) -> Text:
        return "action_ask_appointment_shift_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        department_level2_id = tracker.get_slot("department_level2_id")
        now_datetime = datetime.datetime.now()
        with mysql_session() as session:
            # 查询可挂号班次
            shifts = session.execute(
                select(
                    DoctorSchedule.dept_name,
                    DoctorSchedule.shift_no,
                    DoctorSchedule.start_datetime,
                    DoctorSchedule.end_datetime,
                    func.sum(DoctorSchedule.appointment_limit).label(
                        "appointment_limit"
                    ),
                )
                .where(DoctorSchedule.schedule_date == now_datetime.date())
                .where(DoctorSchedule.end_datetime >= now_datetime)
                .where(DoctorSchedule.dept_id == department_level2_id)
                .where(DoctorSchedule.is_deleted == 0)
                .group_by(
                    DoctorSchedule.dept_id,
                    DoctorSchedule.dept_name,
                    DoctorSchedule.shift_no,
                    DoctorSchedule.start_datetime,
                    DoctorSchedule.end_datetime,
                )
            ).all()

            # 计算每个班次的剩余挂号数
            appointments = session.execute(
                select(Appointment.shift_no, func.count(1).label("used"))
                .where(Appointment.visit_date == now_datetime.date())
                .where(Appointment.dept_id == department_level2_id)
                .where(Appointment.is_deleted == 0)
                .group_by(Appointment.shift_no)
            ).all()

        buttons = []
        shift_used = {a.shift_no: a.used for a in appointments}
        for s in shifts:
            title = (
                f"{s.dept_name}[{s.start_datetime.time()} - {s.end_datetime.time()}]"
            )
            remaining = s.appointment_limit - shift_used.get(s.shift_no, 0)
            if remaining <= 0:
                continue
            title += f"(剩余{remaining})"
            buttons.append(
                {
                    "title": title,
                    "payload": f"/SetSlots(appointment_shift_id={s.shift_no})",
                }
            )

        if not buttons:
            return [
                SlotSet("appointment_shift_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        dispatcher.utter_message(text="请选择时间：", buttons=buttons)


class ValidateAppointmentShift(Action):
    """验证挂号班次"""

    def name(self) -> Text:
        return "action_valid_appointment_shift"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        department_level2_id = tracker.get_slot("department_level2_id")
        appointment_shift_id = tracker.get_slot("appointment_shift_id")
        # 查询是否已经预约过该班次挂号
        with mysql_session() as session:
            have = session.scalar(
                select(Appointment.id)
                .where(Appointment.patient_id == user_id)
                .where(Appointment.dept_id == department_level2_id)
                .where(Appointment.shift_no == appointment_shift_id)
                .where(Appointment.status.in_([1, 2]))
                .where(Appointment.is_deleted == 0)
            )

            if have:
                dispatcher.utter_message(text="您已预约过这个时间段的挂号")
                return [SlotSet("valid_appointment_shift", False)]

            return [SlotSet("valid_appointment_shift", True)]


class AddAppointment(Action):
    """添加挂号预约"""

    def name(self) -> Text:
        return "action_add_appointment"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        department_level2_id = tracker.get_slot("department_level2_id")
        appointment_shift_id = tracker.get_slot("appointment_shift_id")
        try:
            with mysql_session() as session:
                # 查询挂号序号
                queue_no = session.scalar(
                    select(func.max(Appointment.queue_no))
                    .where(Appointment.dept_id == department_level2_id)
                    .where(Appointment.visit_date == datetime.date.today())
                    .where(Appointment.is_deleted == 0)
                )
                queue_no = queue_no + 1 if queue_no else 1
                # 获取挂号的班次
                schedule = session.scalar(
                    select(DoctorSchedule, func.count(Appointment.id))
                    .outerjoin(
                        Appointment, DoctorSchedule.id == Appointment.schedule_id
                    )
                    .where(DoctorSchedule.dept_id == department_level2_id)
                    .where(DoctorSchedule.shift_no == appointment_shift_id)
                    .where(DoctorSchedule.schedule_date == datetime.date.today())
                    .where(DoctorSchedule.is_deleted == 0)
                    .group_by(DoctorSchedule.id)
                    .order_by(func.count(Appointment.id))
                )
                # 查询患者信息
                patient_name = session.scalar(
                    select(Patient.name)
                    .where(Patient.id == user_id)
                    .where(Patient.is_deleted == 0)
                )
                # 创建挂号信息
                appointment = Appointment(
                    patient_id=user_id,
                    patient_name=patient_name,
                    dept_id=department_level2_id,
                    dept_name=schedule.dept_name,
                    doctor_id=schedule.doctor_id,
                    doctor_name=schedule.doctor_name,
                    shift_no=appointment_shift_id,
                    visit_date=schedule.schedule_date,
                    schedule_id=schedule.id,
                    start_datetime=schedule.start_datetime,
                    end_datetime=schedule.end_datetime,
                    queue_no=queue_no,
                    status=1,
                )
                session.add(appointment)
                session.commit()
            dispatcher.utter_message(text="预约成功")
        except Exception as _:
            dispatcher.utter_message(text="预约失败")
        return []


class QueryAppointment(Action):
    """查看已预约的挂号"""

    def name(self) -> Text:
        return "action_query_appointment"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            # 查询当天的已取号和已预约的挂号
            appointments = session.scalars(
                (
                    select(Appointment)
                    .where(Appointment.patient_id == user_id)
                    .where(Appointment.status.in_([1, 2]))
                    .where(Appointment.visit_date == datetime.date.today())
                    .where(Appointment.is_deleted == 0)
                )
            ).all()

        if not appointments:
            dispatcher.utter_message(text="暂无挂号预约")
            return []

        message = "挂号信息：\n"
        for i in appointments:
            visit_date_str = i.visit_date.strftime("%Y-%m-%d")
            start_time_str = i.start_datetime.strftime("%H:%M")
            end_time_str = i.end_datetime.strftime("%H:%M")
            appointment_status_map = {1: "已预约", 2: "已取号"}
            appointment_status = appointment_status_map[i.status]
            message += f"- 科室：{i.dept_name}\n"
            message += f"   - 姓名：{i.patient_name}\n"
            message += f"   - 医生：{i.doctor_name}\n"
            message += f"   - 日期：{visit_date_str}\n"
            message += f"   - 时间：{start_time_str}-{end_time_str}\n"
            message += f"   - 序号：{i.queue_no}\n"
            message += f"   - 状态：{appointment_status}\n"
        dispatcher.utter_message(text=message)
        return []
