from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from .db import mysql_session, process_feedback
from .orm import Feedback


class ReceiveFeedback(Action):
    """处理反馈"""

    def name(self) -> Text:
        return "action_receive_feedback"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_id = tracker.get_slot("user_id")
        feedback_content = tracker.get_slot("feedback_content")
        type, title = process_feedback(feedback_content)
        with mysql_session() as session:
            feedback = Feedback(
                patient_id=user_id,
                type=type,
                title=title,
                content=feedback_content,
                status=1,
            )
            session.add_all([feedback])
            session.commit()
        dispatcher.utter_message(text="已收到您的反馈，我们会尽快处理(‾◡◝)")
