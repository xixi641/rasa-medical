"""生成排班信息"""

import os
import math
import json
import random
import base64
import hashlib
import datetime
import numpy as np
from tqdm import tqdm
from collections import defaultdict
from dataclasses import dataclass, field
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from orm import Doctor, Department



@dataclass
class DoctorState:
    id: int
    name: str
    title: str
    shift_limit: int
    primary_dept_id: int
    shift_count: int = 0
    # {day: {"dept_id-s": (start_datetime, end_datetime)}}
    shifts: dict[datetime.date, dict[str, tuple[datetime.datetime]]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    def add_shift(self, day: datetime.date, dept_id: int, s: int, time: dict[str, str]):
        """向 该天 添加 科室-班次:起始时间"""
        start_time = datetime.datetime.strptime(time["start"], "%H:%M").time()
        end_time = datetime.datetime.strptime(time["end"], "%H:%M").time()
        start_datetime = datetime.datetime.combine(day, start_time)
        end_datetime = datetime.datetime.combine(day, end_time)
        if end_time < start_time:
            end_datetime += datetime.timedelta(days=1)
        self.shifts[day][f"{dept_id}-{s}"] = (start_datetime, end_datetime)
        self.shift_count += 1

    def remove_shift(self, day: datetime.date, dept_id: int, s: int):
        """从 该天 移除 科室-班次:起始时间"""
        del self.shifts[day][f"{dept_id}-{s}"]
        self.shift_count -= 1

    def get_all_shifts_time(self):
        """获取该医生所有排班时间"""
        all_shifts_time = sorted(
            (shift for day in self.shifts for shift in self.shifts[day].values()),
            key=lambda x: x[0],
        )
        return all_shifts_time

    def limit_penalty(self) -> float:
        """超排班上限惩罚"""
        limit_penalty = 0.0
        if self.shift_count > self.shift_limit:
            limit_penalty = (self.shift_count - self.shift_limit) ** 2
        return limit_penalty

    def no_morning_penalty(self) -> float:
        """主任与副主任医师排班不在上午惩罚"""
        no_morning_penalty = 0.0
        if self.title not in ["主任医师", "副主任医师"]:
            return no_morning_penalty
        all_shifts_time = self.get_all_shifts_time()
        for shift in all_shifts_time:
            start_time = shift[0]
            if start_time.hour > 12:
                no_morning_penalty += 1
        return no_morning_penalty

    def near_shift_penalty(self) -> float:
        """相邻排班小于12小时惩罚(忽略跨周情况)"""
        near_shift_penalty = 0.0
        prev_end_time = None
        if not self.shifts:
            return near_shift_penalty
        all_shifts_time = self.get_all_shifts_time()
        for shift in all_shifts_time:
            start_time = shift[0]
            end_time = shift[1]
            if prev_end_time:
                delta_time = start_time - prev_end_time
                if delta_time < datetime.timedelta(hours=12):
                    near_shift_penalty += (12 - delta_time.total_seconds() / 3600) ** 2
            prev_end_time = end_time
        return near_shift_penalty


@dataclass
class DepartmentState:
    id: int
    name: str
    schedule: list[dict[str, str]]
    doctors: list[int]
    req_per_shift: list[int]
    # {day: {s1: (doctor_ids), s2: (doctor_ids)}}
    shifts: dict[datetime.date, dict[int, set[int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )

    def add_shift(self, day: datetime.date, s: int, doctor_id: int):
        """向 天:班次 添加 医生"""
        self.shifts[day][s].add(doctor_id)

    def remove_shift(self, day: datetime.date, s: int, doctor_id: int):
        """从 天:班次 移除 医生"""
        self.shifts[day][s].remove(doctor_id)

    def shift_doctor_nums(self, day: datetime.date, s: int) -> int:
        """返回该天该班次医生数"""
        return len(self.shifts[day][s])

    def shift_req_nums(self, s: int) -> int:
        """返回该天该班次所需医生数"""
        return self.req_per_shift[s]

    def cover_penalty(self) -> float:
        """计算覆盖不足/超配惩罚"""
        cover_penalty = 0.0
        for day in self.shifts:
            for s in range(len(self.schedule)):
                cover_penalty += (
                    self.shift_doctor_nums(day, s) - self.shift_req_nums(s)
                ) ** 2
        return cover_penalty


class ScheduleState:
    def __init__(
        self,
        days: list[datetime.date],
        departments: list[Department],
        dept_doctors: dict[int, list[Doctor]],
        req_per_shift: list[int],
    ):
        self.op_stack = []
        self.days = days
        self.doctor_states: dict[int, DoctorState] = {
            d.id: DoctorState(
                id=d.id,
                name=d.name,
                title=d.title,
                shift_limit=d.shift_limit,
                primary_dept_id=d.primary_dept_id,
            )
            for doctors in dept_doctors.values()
            for d in doctors
        }
        self.dept_states: dict[int, DepartmentState] = {
            d.id: DepartmentState(
                id=d.id,
                name=d.name,
                schedule=d.schedule,
                doctors=[doctor.id for doctor in dept_doctors[d.id]],
                req_per_shift=req_per_shift[: len(d.parent.shift_item.schedule)],
            )
            for d in departments
        }
        self.all_shifts = {
            dept_state.id: [(day, s) for s in range(len(dept_state.schedule))]
            for day in self.days
            for dept_state in self.dept_states.values()
        }

    def add_shift(
        self,
        day: datetime.date,
        s: int,
        dept_id: int,
        doctor_id: int,
    ):
        """添加排班"""
        time = self.dept_states[dept_id].schedule[s]
        self.doctor_states[doctor_id].add_shift(day, dept_id, s, time)
        self.dept_states[dept_id].add_shift(day, s, doctor_id)
        self.op_stack.append(
            {
                "op": "add",
                "day": day,
                "s": s,
                "dept_id": dept_id,
                "doctor_id": doctor_id,
            }
        )

    def remove_shift(
        self,
        day: datetime.date,
        s: int,
        dept_id: int,
        doctor_id: int,
    ):
        """移除排班"""
        self.doctor_states[doctor_id].remove_shift(day, dept_id, s)
        self.dept_states[dept_id].remove_shift(day, s, doctor_id)
        self.op_stack.append(
            {
                "op": "remove",
                "day": day,
                "s": s,
                "dept_id": dept_id,
                "doctor_id": doctor_id,
            }
        )

    def initialize(self):
        """生成初始解"""
        for dept_id in self.dept_states:
            doctor_ids = self.dept_states[dept_id].doctors
            for day in self.days:
                for s, time in enumerate(self.dept_states[dept_id].schedule):
                    # 按 已分配少→随机打散 排序
                    candidate_doctor_ids = sorted(
                        doctor_ids,
                        key=lambda x: (
                            self.doctor_states[x].shift_count,
                            random.random(),
                        ),
                    )
                    for doctor_id in candidate_doctor_ids:
                        # 班次全覆盖则结束
                        if self.dept_states[dept_id].shift_doctor_nums(
                            day, s
                        ) >= self.dept_states[dept_id].shift_req_nums(s):
                            break
                        # 避免同日多班
                        if day in self.doctor_states[doctor_id].shifts:
                            continue
                        self.add_shift(day, s, dept_id, doctor_id)

    def cost(
        self,
        w_cover: float,  # 覆盖不足/超配惩罚
        w_limit: float,  # 超排班上限惩罚
        w_balance: float,  # 归一化均衡惩罚
        w_near_shift: float,  # 相邻排班小于12小时惩罚
        w_no_morning: float,  # 主任与副主任医师排班不在上午惩罚
    ) -> tuple[float, dict[str, float]]:
        """代价函数"""
        # 覆盖不足/超配惩罚
        cover_penalty = sum([d.cover_penalty() for d in self.dept_states.values()])

        limit_penalty = 0.0
        near_shift_penalty = 0.0
        no_morning_penalty = 0.0
        for d in self.doctor_states.values():
            # 超排班上限惩罚
            limit_penalty += d.limit_penalty()
            # 相邻排班小于12小时惩罚
            near_shift_penalty += d.near_shift_penalty()
            # 主任与副主任医师排班不在上午惩罚
            no_morning_penalty += d.no_morning_penalty()

        # 归一化均衡惩罚
        # 找出每个科室所有主属科室为该科室的医生
        balance_penalty = 0.0
        for d in self.dept_states.values():
            primary_doctors = [
                self.doctor_states[doctor_id]
                for doctor_id in d.doctors
                if self.doctor_states[doctor_id].primary_dept_id == d.id
            ]
            shift_ratios = [
                float(doctor.shift_count) / float(doctor.shift_limit)
                for doctor in primary_doctors
                if doctor.shift_limit > 0
            ]
            if shift_ratios:
                balance_penalty += np.var(shift_ratios)

        return (
            w_cover * cover_penalty
            + w_limit * limit_penalty
            + w_balance * balance_penalty
            + w_no_morning * no_morning_penalty
            + w_near_shift * near_shift_penalty,
            {
                "cover_penalty": cover_penalty,
                "limit_penalty": limit_penalty,
                "balance_penalty": balance_penalty,
                "no_morning_penalty": no_morning_penalty,
                "near_shift_penalty": near_shift_penalty,
            },
        )

    def random_neighbor(self):
        """
        产生邻域解
        - 替换一个班次的一名医生
        - 交换两个班次的一名医生
        - 将一名医生从一个班次移动到另一个班次
        """
        self.op_stack.clear()
        dept_state = random.choice(list(self.dept_states.values()))
        dept_all_shifts = self.all_shifts[dept_state.id]
        op = random.choices([1, 2, 3, 4, 5], weights=[0.3, 0.3, 0.3, 0.05, 0.05], k=1)[
            0
        ]
        # 收集非空班次
        non_empty_shifts = [
            (day, s)
            for day in self.days
            for s in range(len(dept_state.schedule))
            if dept_state.shift_doctor_nums(day, s)
        ]

        # 替换一个班次的一名医生
        if op == 1 and non_empty_shifts:
            # 选择日期和班次
            day, s = random.choice(non_empty_shifts)
            # 选择要替换的医生
            src_doctor_ids = list(dept_state.shifts[day][s])
            src_doctor_id = random.choice(src_doctor_ids)
            # 选择目标医生
            tgt_doctor_id = random.choice(dept_state.doctors)
            # 避免自己替换自己或重复添加
            if tgt_doctor_id != src_doctor_id and tgt_doctor_id not in src_doctor_ids:
                self.remove_shift(day, s, dept_state.id, src_doctor_id)
                self.add_shift(day, s, dept_state.id, tgt_doctor_id)

        # 交换两个班次的一名医生
        elif op == 2 and len(non_empty_shifts) >= 2:
            (day1, s1), (day2, s2) = random.sample(non_empty_shifts, 2)
            doctor_ids1 = list(dept_state.shifts[day1][s1])
            doctor_ids2 = list(dept_state.shifts[day2][s2])
            doctor_id1 = random.choice(doctor_ids1)
            doctor_id2 = random.choice(doctor_ids2)
            # 避免自己替换自己或重复添加
            if (
                doctor_id1 != doctor_id2
                and doctor_id1 not in doctor_ids2
                and doctor_id2 not in doctor_ids1
            ):
                self.remove_shift(day1, s1, dept_state.id, doctor_id1)
                self.remove_shift(day2, s2, dept_state.id, doctor_id2)
                self.add_shift(day1, s1, dept_state.id, doctor_id2)
                self.add_shift(day2, s2, dept_state.id, doctor_id1)

        # 将一名医生从一个班次移动到另一个班次
        elif op == 3 and non_empty_shifts:
            src_day, src_s = random.choice(non_empty_shifts)
            doctor_id = random.choice(list(dept_state.shifts[src_day][src_s]))
            tgt_day, tgt_s = random.choice(dept_all_shifts)
            tgt_doctor_ids = dept_state.shifts[tgt_day][tgt_s]
            # 避免原地移动或重复添加
            if (src_day, src_s) != (
                tgt_day,
                tgt_s,
            ) and doctor_id not in tgt_doctor_ids:
                self.remove_shift(src_day, src_s, dept_state.id, doctor_id)
                self.add_shift(tgt_day, tgt_s, dept_state.id, doctor_id)

        # 向一个班次添加一名医生
        elif op == 4:
            day, s = random.choice(dept_all_shifts)
            doctor_id = random.choice(dept_state.doctors)
            doctor_ids = list(dept_state.shifts[day][s])
            # 避免重复添加
            if doctor_id not in doctor_ids:
                self.add_shift(day, s, dept_state.id, doctor_id)

        # 从一个班次移除一名医生
        elif op == 5:
            day, s = random.choice(non_empty_shifts)
            doctor_id = random.choice(list(dept_state.shifts[day][s]))
            self.remove_shift(day, s, dept_state.id, doctor_id)

    def rollback(self):
        """回滚"""
        undo_stack = self.op_stack.copy()
        while undo_stack:
            op = undo_stack.pop()
            if op["op"] == "add":
                self.remove_shift(op["day"], op["s"], op["dept_id"], op["doctor_id"])
            elif op["op"] == "remove":
                self.add_shift(op["day"], op["s"], op["dept_id"], op["doctor_id"])

    def copy_dept_shifts(self):
        """拷贝各科室排班信息"""
        return {
            dept_id: {
                day: {s: doctor_set.copy() for s, doctor_set in shifts.items()}
                for day, shifts in dept_state.shifts.items()
            }
            for dept_id, dept_state in self.dept_states.items()
        }

    def simulated_annealing(
        self,
        max_iter: int = 10000,  # 最大迭代次数
        temperature_0: float = 20.0,  # 初始温度
        alpha: float = 0.99,  # 温度下降因子
        w_cover: float = 40.0,  # 覆盖不足/超配惩罚
        w_limit: float = 1.0,  # 超排班上限惩罚
        w_balance: float = 10.0,  # 归一化均衡惩罚
        w_near_shift: float = 1.0,  # 相邻排班小于12小时惩罚
        w_no_morning: float = 1.0,  # 主任与副主任医师排班不在上午惩罚
        patience: int = 2000,  # 早停
    ):
        """模拟退火法生成排班信息"""
        self.initialize()
        cur_cost, cur_parts = self.cost(
            w_cover,
            w_limit,
            w_balance,
            w_near_shift,
            w_no_morning,
        )
        best = self.copy_dept_shifts()
        best_cost = cur_cost
        best_parts = cur_parts

        temperature = temperature_0
        stall = 0

        tqdm_bar = tqdm(range(max_iter), desc="生成排班")
        for _ in tqdm_bar:
            self.random_neighbor()
            new_cost, new_parts = self.cost(
                w_cover,
                w_limit,
                w_balance,
                w_near_shift,
                w_no_morning,
            )
            delta = new_cost - cur_cost
            # 是否更新当前解
            if delta < 0 or random.random() < math.exp(-delta / max(temperature, 1e-9)):
                cur_cost, cur_parts = new_cost, new_parts
                # 是否更新最优解
                if cur_cost < best_cost:
                    best = self.copy_dept_shifts()
                    best_cost, best_parts = cur_cost, cur_parts
                    stall = 0
                else:
                    stall += 1
            else:
                self.rollback()
                stall += 1
            temperature *= alpha
            if stall >= patience:
                break
            tqdm_bar.set_postfix({"best": best_cost, "current": cur_cost})
        return best


def gen_emr_content() -> dict[str, str]:
    """生成电子病历内容"""

    # 主诉
    chief_complaints = [
        "咳嗽、咳痰3天",
        "发热伴头痛2天",
        "胸痛胸闷1周",
        "腹痛腹泻半天",
        "头晕乏力2天",
        "咽痛咽干1天",
        "关节疼痛3天",
        "恶心呕吐1天",
        "呼吸困难2小时",
        "皮疹瘙痒1周",
        "尿频尿急尿痛1天",
        "心悸气短3天",
        "失眠多梦1周",
        "食欲不振2天",
        "体重下降1个月",
    ]

    # 现病史
    present_illnesses = [
        "患者3天前受凉后出现咳嗽，咳少量白痰，无发热，口服止咳药物效果不佳。",
        "患者2天前出现发热，体温最高38.5℃，伴有头痛，无恶心呕吐。",
        "患者1周前出现胸痛胸闷，活动后加重，休息后可缓解。",
        "患者半天前出现腹痛腹泻，大便4-5次/日，为稀便，伴有里急后重感。",
        "患者2天前出现头晕乏力，伴有心慌，测血压偏低。",
        "患者1天前出现咽痛咽干，吞咽时加重，伴有声音嘶哑。",
        "患者3天前出现关节疼痛，以膝关节为主，活动受限。",
        "患者1天前出现恶心呕吐，呕吐胃内容物2次，伴有腹胀。",
        "患者2小时前出现呼吸困难，伴有喘息，既往有哮喘病史。",
        "患者1周前出现皮疹瘙痒，以躯干为主，无发热。",
        "患者1天前出现尿频尿急尿痛，伴有尿道口灼热感。",
        "患者3天前出现心悸气短，活动后加重，夜间可平卧。",
        "患者1周前出现失眠多梦，入睡困难，易醒。",
        "患者2天前出现食欲不振，伴有腹胀，大便正常。",
        "患者1个月来体重下降5公斤，伴有乏力。",
    ]

    # 诊断
    diagnoses = [
        "急性上呼吸道感染",
        "社区获得性肺炎",
        "冠心病，心绞痛",
        "急性胃肠炎",
        "高血压病1级",
        "急性咽炎",
        "类风湿性关节炎",
        "急性胃炎",
        "支气管哮喘急性发作",
        "过敏性皮炎",
        "急性膀胱炎",
        "心律失常",
        "神经衰弱",
        "功能性消化不良",
        "甲状腺功能亢进",
    ]

    # 处方
    prescriptions = [
        "阿莫西林胶囊 0.5g tid 7天",
        "头孢克肟分散片 0.1g bid 5天",
        "硝酸甘油片 0.5mg 舌下含服 必要时",
        "蒙脱石散 3g tid 3天",
        "氨氯地平片 5mg qd",
        "蒲地蓝消炎口服液 10ml tid 7天",
        "甲氨蝶呤片 7.5mg qw",
        "奥美拉唑肠溶胶囊 20mg qd 14天",
        "沙丁胺醇气雾剂 1喷 q4h 必要时",
        "氯雷他定片 10mg qd 7天",
        "左氧氟沙星片 0.5g qd 7天",
        "美托洛尔缓释片 47.5mg qd",
        "佐匹克隆片 7.5mg qn",
        "多潘立酮片 10mg tid 餐前",
        "甲巯咪唑片 5mg tid",
    ]

    return {
        "主诉": random.choice(chief_complaints),
        "现病史": random.choice(present_illnesses),
        "诊断": random.choice(diagnoses),
        "处方": random.choice(prescriptions),
    }


private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)


def gen_emr_signature(emr_content: dict, sign_datetime: datetime) -> dict:
    """生成电子签名"""
    cert_sn = os.urandom(10).hex().upper()
    signed_at = sign_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    ip = ".".join(str(random.randint(1, 255)) for _ in range(4))
    content_str = json.dumps(emr_content, ensure_ascii=False, sort_keys=True)
    hash_value = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    signature = private_key.sign(
        content_str.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
    )
    sign_value = base64.b64encode(signature).decode("utf-8")
    return {
        "sign_value": sign_value,
        "cert_sn": cert_sn,
        "cert_issuer": "CN=China Health CA, O=National Health Commission",
        "signed_at": signed_at,
        "algorithm": "SHA256withRSA",
        "hash_value": hash_value,
        "device_info": {"ip": ip, "user_agent": "EMR System v3.1"},
    }
