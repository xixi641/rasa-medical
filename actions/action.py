from typing import Any, Text, Dict, List

from rasa_sdk.events import SlotSet
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from time import sleep
from sqlalchemy import select
from .db import mysql_session
from .orm import Patient


class UserCheck(Action):
    """检查用户是否存在"""

    def name(self) -> Text:
        return "action_user_check"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        with mysql_session() as session:
            patient = session.execute(
                select(Patient).where(Patient.id == user_id)
            ).scalar_one_or_none()
        if patient:
            return [SlotSet("user_id", user_id)]
        else:
            return [SlotSet("user_id", None)]


class InitiatePayment(Action):
    """发起支付"""

    def name(self) -> Text:
        return "action_initiate_payment"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="请进行支付")
        dispatcher.utter_message(image="https://i.postimg.cc/BvHmkjG8/image.jpg")
        # 返回支付单号
        return [SlotSet("payment_id", "1234567890")]


class CheckPaymentStatus(Action):
    """检查支付状态"""

    def name(self) -> Text:
        return "action_check_payment_status"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        payment_id = tracker.get_slot("payment_id")
        sleep(2)

        if not payment_id:
            dispatcher.utter_message(text="支付遇到问题，请重新支付")
            return [SlotSet("payed", False)]

        dispatcher.utter_message(text="支付成功")
        return [SlotSet("payed", True)]
