from typing import Any, Text, Dict, List

from rasa_sdk.events import SlotSet, ActionExecutionRejected
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

import datetime
from sqlalchemy import select, func
from .db import mysql_session
from .orm import (
    Patient,
    ShiftItem,
    ExaminationItem,
    ExaminationBooking,
    ExaminationReport,
)


class AskExaminationId(Action):
    """获取检查项目id"""

    def name(self) -> Text:
        return "action_ask_examination_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        with mysql_session() as session:
            # 查询检查项目
            examinations = session.scalars(
                select(ExaminationItem).where(ExaminationItem.is_deleted == 0)
            ).all()

        if not examinations:
            return [
                SlotSet("examination_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        for i in examinations:
            buttons.append(
                {
                    "title": f"{i.name}",
                    "payload": f"/SetSlots(examination_id={i.id})",
                }
            )
        dispatcher.utter_message(text="请选择检查项目：", buttons=buttons)
        return []


class AskExaminationDate(Action):
    """获取检查日期"""

    def name(self) -> Text:
        return "action_ask_examination_date"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        today = datetime.date.today()
        candidate_dates = [
            today + datetime.timedelta(days=i) for i in range(6 - today.weekday())
        ]

        if not candidate_dates:
            return [
                SlotSet("examination_date", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        for date in candidate_dates:
            buttons.append(
                {
                    "title": f"{date}",
                    "payload": f"/SetSlots(examination_date={date})",
                }
            )
        dispatcher.utter_message(text="请选择检查日期：", buttons=buttons)
        return []


class AskExaminationShiftId(Action):
    """获取班次序号"""

    def name(self) -> Text:
        return "action_ask_examination_shift_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        examination_date = tracker.get_slot("examination_date")
        examination_date = datetime.datetime.strptime(
            examination_date, "%Y-%m-%d"
        ).date()
        now_datetime = datetime.datetime.now()
        with mysql_session() as session:
            # 查询检查班次
            shift = session.scalars(
                select(ShiftItem)
                .where(ShiftItem.name == "outpatient")
                .where(ShiftItem.is_deleted == 0)
            ).one_or_none()

        if not shift:
            return [
                SlotSet("examination_shift_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        shift_datetimes = []
        for schedule in shift.schedule:
            start_time = schedule["start"]
            end_time = schedule["end"]
            start_time = datetime.datetime.strptime(start_time, "%H:%M").time()
            end_time = datetime.datetime.strptime(end_time, "%H:%M").time()
            start_datetime = datetime.datetime.combine(examination_date, start_time)
            end_datetime = datetime.datetime.combine(examination_date, end_time)
            if end_time < start_time:
                end_datetime += datetime.timedelta(days=1)
            shift_datetimes.append((start_datetime, end_datetime))

        if not shift_datetimes:
            return [
                SlotSet("examination_shift_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        shift_datetimes.sort(key=lambda x: x[0])
        for i, shift_datetime in enumerate(shift_datetimes):
            if now_datetime > shift_datetime[1]:
                continue
            start_datetime = shift_datetime[0].strftime("%H:%M")
            end_datetime = shift_datetime[1].strftime("%H:%M")
            buttons.append(
                {
                    "title": f"{start_datetime} ~ {end_datetime}",
                    "payload": f"/SetSlots(examination_shift_id={i})",
                }
            )

        if not buttons:
            return [
                SlotSet("examination_shift_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        dispatcher.utter_message(text="请选择时间：", buttons=buttons)
        return []


class AddExaminationBooking(Action):
    """添加检查预约"""

    def name(self) -> Text:
        return "action_add_examination_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        examination_id = tracker.get_slot("examination_id")
        examination_date = tracker.get_slot("examination_date")
        examination_date = datetime.datetime.strptime(
            examination_date, "%Y-%m-%d"
        ).date()
        examination_shift_id = tracker.get_slot("examination_shift_id")
        examination_shift_id = int(examination_shift_id)
        try:
            with mysql_session() as session:
                # 查询预约检查序号
                queue_no = session.scalar(
                    select(func.max(ExaminationBooking.queue_no))
                    .where(ExaminationBooking.examination_item_id == examination_id)
                    .where(ExaminationBooking.examination_date == examination_date)
                    .where(ExaminationBooking.is_deleted == 0)
                )
                queue_no = queue_no + 1 if queue_no else 1
                # 获取预约检查的班次
                shift = session.scalars(
                    select(ShiftItem)
                    .where(ShiftItem.name == "outpatient")
                    .where(ShiftItem.is_deleted == 0)
                ).one_or_none()
                # 查询患者信息
                patient_name = session.scalar(
                    select(Patient.name)
                    .where(Patient.id == user_id)
                    .where(Patient.is_deleted == 0)
                )
                # 查询检查项目名称
                examination_name = session.scalar(
                    select(ExaminationItem.name)
                    .where(ExaminationItem.id == examination_id)
                    .where(ExaminationItem.is_deleted == 0)
                )

                shift_datetimes = []
                for schedule in shift.schedule:
                    start_time = schedule["start"]
                    end_time = schedule["end"]
                    start_time = datetime.datetime.strptime(start_time, "%H:%M").time()
                    end_time = datetime.datetime.strptime(end_time, "%H:%M").time()
                    start_datetime = datetime.datetime.combine(
                        examination_date, start_time
                    )
                    end_datetime = datetime.datetime.combine(examination_date, end_time)
                    if end_time < start_time:
                        end_datetime += datetime.timedelta(days=1)
                    shift_datetimes.append((start_datetime, end_datetime))
                shift_datetimes.sort(key=lambda x: x[0])
                examination_start_datetime = shift_datetimes[examination_shift_id][0]
                examination_end_datetime = shift_datetimes[examination_shift_id][1]

                # 创建检查预约
                examination_order = ExaminationBooking(
                    patient_id=user_id,
                    patient_name=patient_name,
                    examination_item_id=examination_id,
                    examination_item_name=examination_name,
                    examination_date=examination_date,
                    start_datetime=examination_start_datetime,
                    end_datetime=examination_end_datetime,
                    queue_no=queue_no,
                    status=1,
                )
                session.add(examination_order)
                session.commit()
            dispatcher.utter_message(text="预约成功")
        except Exception as e:
            print(e)
            dispatcher.utter_message(text="预约失败")
        return []


class QueryExaminationBooking(Action):
    """查看已预约的检查"""

    def name(self) -> Text:
        return "action_query_examination_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            # 查询已预约的检查
            examination_bookings = session.scalars(
                (
                    select(ExaminationBooking)
                    .where(ExaminationBooking.patient_id == user_id)
                    .where(ExaminationBooking.status == 1)
                    .where(ExaminationBooking.examination_date >= datetime.date.today())
                )
            ).all()

        if not examination_bookings:
            dispatcher.utter_message(text="暂无已预约的检查")
            return []

        message = "预约检查：\n"
        for i in examination_bookings:
            visit_date_str = i.examination_date.strftime("%Y-%m-%d")
            start_time_str = i.start_datetime.strftime("%H:%M")
            end_time_str = i.end_datetime.strftime("%H:%M")
            message += f"- 检查：{i.examination_item_name}\n"
            message += f"   - 姓名：{i.patient_name}\n"
            message += f"   - 日期：{visit_date_str}\n"
            message += f"   - 时间：{start_time_str}-{end_time_str}\n"
            message += f"   - 序号：{i.queue_no}\n"
            message += "   - 状态：已预约\n"
        dispatcher.utter_message(text=message)
        return []


class AskExaminationReportId(Action):
    """获取检查报告id"""

    def name(self) -> Text:
        return "action_ask_examination_report_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            # 查询检查报告
            examination_reports = session.scalars(
                (
                    select(ExaminationReport)
                    .where(ExaminationReport.patient_id == user_id)
                    .where(ExaminationReport.is_deleted == 0)
                )
            ).all()

        if not examination_reports:
            return [
                SlotSet("examination_report_id", ""),
                ActionExecutionRejected("action_listen"),
            ]

        buttons = []
        for i in examination_reports:
            buttons.append(
                {
                    "title": f"【{i.examination_item_name}】{i.patient_name}-[{i.examination_time}]",
                    "payload": f"/SetSlots(examination_report_id={i.id})",
                }
            )
        dispatcher.utter_message(text="请选择检查报告：", buttons=buttons)
        return []


class QueryExaminationReport(Action):
    """查询检查报告"""

    def name(self) -> Text:
        return "action_query_examination_report"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        examination_report_id = tracker.get_slot("examination_report_id")
        with mysql_session() as session:
            # 查询检查报告
            examination_report = session.scalars(
                select(ExaminationReport)
                .where(ExaminationReport.id == examination_report_id)
                .where(ExaminationReport.is_deleted == 0)
            ).one_or_none()

        if not examination_report:
            dispatcher.utter_message(text="无法查询该检查报告")
            return []

        message = f"- 患者：{examination_report.patient_name}\n"
        message += f"- 检查：{examination_report.examination_item_name}\n"
        message += f"- 时间：{examination_report.examination_time}\n"
        message += f"- 总结：{examination_report.summary}\n"
        message += f"- 报告下载：{examination_report.pdf_url}\n"
        dispatcher.utter_message(text=message)
        return []
