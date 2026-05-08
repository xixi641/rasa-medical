from typing import Any, Text, Dict, List

from rasa_sdk.events import SlotSet, ActionExecutionRejected
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from sqlalchemy import select, func
from .db import mysql_session
from .orm import Emr


class AskEMRId(Action):
    """获取病历id"""

    def name(self) -> Text:
        return "action_ask_emr_id"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            latest_emr_per_case = (
                select(Emr.case_id, func.max(Emr.version))
                .where(Emr.patient_id == user_id)
                .where(Emr.is_deleted == 0)
                .group_by(Emr.case_id)
                .subquery()
            )
            # 查询病历
            emrs = session.scalars(
                select(Emr).join(
                    latest_emr_per_case,
                    (Emr.case_id == latest_emr_per_case.c.case_id)
                    & (Emr.version == latest_emr_per_case.c.max),
                )
            ).all()

        if not emrs:
            return [SlotSet("emr_id", ""), ActionExecutionRejected("action_listen")]

        buttons = []
        for emr in emrs:
            title = (
                f"{emr.case_id}-{emr.emr_type}-{emr.patient_name} [{emr.create_time}]"
            )
            buttons.append(
                {
                    "title": title,
                    "payload": f"/SetSlots(emr_id={emr.id})",
                }
            )
        dispatcher.utter_message(text="请选择病历：", buttons=buttons)
        return []


class QueryEMR(Action):
    """查询病历"""

    def name(self) -> Text:
        return "action_query_emr"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        emr_id = tracker.get_slot("emr_id")
        with mysql_session() as session:
            # 查询病历
            emr = session.scalars(
                select(Emr).where(Emr.id == emr_id).where(Emr.is_deleted == 0)
            ).one_or_none()

        if not emr:
            dispatcher.utter_message(text="无此病历")
            return []

        message = f"- 病历类型：{emr.emr_type}\n"
        message += f"- 患者：{emr.patient_name}\n"
        message += f"- 医生：{emr.doctor_name}\n"
        message += "- 详情：\n"
        for k, v in emr.content.items():
            message += f"   - {k}：{v}\n"
        message += f"- 时间：{emr.create_time}\n"
        dispatcher.utter_message(text=message)
        return []
