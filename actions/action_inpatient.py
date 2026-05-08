from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

import datetime
from sqlalchemy import select
from .db import mysql_session
from .orm import InpatientBooking, InpatientRecord


class QueryInpatientBooking(Action):
    """查询住院预约"""

    def name(self) -> Text:
        return "action_query_inpatient_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            # 查询住院预约
            inpatients = session.scalars(
                select(InpatientBooking)
                .where(InpatientBooking.patient_id == user_id)
                .where(InpatientBooking.status.in_([1, 2]))
                .where(InpatientBooking.is_deleted == 0)
            ).all()

        if not inpatients:
            dispatcher.utter_message(text="暂无住院预约")
            return []

        status_map = {1: "排队中", 2: "已预约"}
        bed_type_map = {1: "普通", 2: "单人间", 3: "ICU"}
        message = "住院预约：\n"
        for i in inpatients:
            message += f"- 科室：{i.dept_name}\n"
            message += f"   - 患者：{i.patient_name}\n"
            message += f"   - 病床类型：{bed_type_map[i.bed_type]}\n"
            message += f"   - 预约状态：{status_map[i.status]}\n"
            message += f"   - 发起时间：{i.create_time}\n"
            if i.expected_date:
                message += f"   - 入院日期：{i.expected_date}\n"
        dispatcher.utter_message(text=message)
        return []


class QueryInpatient(Action):
    """查询住院信息"""

    def name(self) -> Text:
        return "action_query_inpatient"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            # 查询住院信息
            inpatients = session.scalars(
                select(InpatientRecord)
                .where(InpatientRecord.patient_id == user_id)
                .where(InpatientRecord.is_deleted == 0)
            ).all()

        if not inpatients:
            dispatcher.utter_message(text="暂无住院信息")
            return []

        candidate_inpatients = [
            i
            for i in inpatients
            if i.status == 1
            or (
                i.status == 2
                and datetime.datetime.now() - i.discharge_time
                <= datetime.timedelta(days=30)
            )
        ]

        if not candidate_inpatients:
            dispatcher.utter_message(text="暂无住院信息")
            return []

        status_map = {1: "在院", 2: "已出院"}
        bed_type_map = {1: "普通", 2: "单人间", 3: "ICU"}
        message = "住院信息：\n"
        for i in candidate_inpatients:
            message += f"- 科室：{i.dept_name}\n"
            message += f"   - 患者：{i.patient_name}\n"
            message += f"   - 医生：{i.doctor_name}\n"
            message += f"   - 病床类型：{bed_type_map[i.bed_type]}\n"
            message += f"   - 床位号：{i.bed_no}\n"
            message += f"   - 住院状态：{status_map[i.status]}\n"
            message += f"   - 入院时间：{i.admission_time}\n"
            if i.discharge_time:
                message += f"   - 出院时间：{i.discharge_time}\n"
        dispatcher.utter_message(text=message)
        return []
