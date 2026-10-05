"""SAMS - School Activity Management System
รัน:  python app.py   แล้วเปิด http://127.0.0.1:5000
"""
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "sams.db")

app = Flask(__name__)
app.secret_key = "sams-dev-secret-change-me"

ATTEND_LABEL = {"present": "มา", "late": "สาย", "absent": "ขาด", "excused": "ลา"}
app.jinja_env.globals["ATTEND_LABEL"] = ATTEND_LABEL


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def q(sql, args=(), one=False):
    cur = db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    cur = db().execute(sql, args)
    db().commit()
    return cur


def init_db():
    con = sqlite3.connect(DB_PATH)
    with open(os.path.join(BASE, "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    con.execute("PRAGMA foreign_keys = ON")
    seed(con)
    con.commit()
    con.close()


def seed(con):
    random.seed(7)
    con.executemany("INSERT INTO role(role_name) VALUES (?)",
                    [("admin",), ("teacher",), ("student",)])
    con.executemany("INSERT INTO academic_year(year_name,semester) VALUES (?,?)",
                    [("2568", 2), ("2569", 1)])
    con.executemany("INSERT INTO activity_type(type_name) VALUES (?)",
                    [("เข้าค่าย",), ("กีฬาสี",), ("วันวิชาการ",), ("จิตอาสา",),
                     ("ชุมนุม",), ("ค่ายอบรม",)])
    teachers = [("ครูสมชาย ใจดี", "วิทยาศาสตร์", "081-111-1111"),
                ("ครูสุดา รักเรียน", "ภาษาไทย", "081-222-2222"),
                ("ครูวิชัย กีฬาดี", "สุขศึกษา", "081-333-3333"),
                ("ครูนภา ศิลป์งาม", "ศิลปะ", "081-444-4444")]
    con.executemany("INSERT INTO teacher(teacher_name,department,phone) VALUES (?,?,?)", teachers)
    firsts = ["กิตติ", "ณัฐ", "ธนา", "พิมพ์", "อรุณ", "ชลธิชา", "ปิยะ", "สุภา",
              "วีร์", "มนัส", "ลลิตา", "ภูมิ", "ศศิ", "ธีร์", "นุช"]
    lasts = ["สุขใจ", "แสงทอง", "วงศ์ดี", "มั่นคง", "ใจเย็น", "รุ่งเรือง", "บุญมา", "ศรีสุข"]
    for i in range(15):
        con.execute("INSERT INTO student(first_name,last_name,grade,room) VALUES (?,?,?,?)",
                    (firsts[i], random.choice(lasts), f"ม.{random.choice([4,5,6])}", str(random.randint(1, 3))))
    today = date.today()
    acts = [  # name,type,year,location,days offset,start,end,max,hours
        ("ค่ายลูกเสือ-เนตรนารี", 1, 2, "ค่ายลูกเสือจังหวัด", -20, "08:00", "16:00", 40, 8),
        ("กีฬาสีประจำปี", 2, 2, "สนามกีฬาโรงเรียน", -10, "08:30", "15:30", 100, 6),
        ("วันวิชาการ", 3, 2, "อาคารเรียน 1", -3, "09:00", "15:00", 80, 5),
        ("จิตอาสาพัฒนาชุมชน", 4, 2, "วัดใกล้โรงเรียน", 0, "08:00", "12:00", 30, 4),
        ("ชุมนุมหุ่นยนต์", 5, 2, "ห้องคอมพิวเตอร์", 2, "15:30", "17:00", 20, 1.5),
        ("ค่ายอบรมภาวะผู้นำ", 6, 2, "ห้องประชุมใหญ่", 7, "09:00", "16:00", 40, 7),
    ]
    for a in acts:
        d = (today + timedelta(days=a[4])).isoformat()
        con.execute("""INSERT INTO activity(activity_name,type_id,year_id,location,activity_date,
                       start_time,end_time,max_participants,hours) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (a[0], a[1], a[2], a[3], d, a[5], a[6], a[7], a[8]))
    duties = ["หัวหน้าฝ่าย", "ดูแลนักเรียน", "ประเมินผล"]
    for aid in range(1, 7):
        for tid in random.sample(range(1, 5), 2):
            con.execute("INSERT INTO activity_teacher VALUES (?,?,?)", (aid, tid, random.choice(duties)))
    hours = {i + 1: a[8] for i, a in enumerate(acts)}
    for aid in range(1, 7):
        for sid in random.sample(range(1, 16), random.randint(7, 12)):
            cur = con.execute("INSERT INTO registration(activity_id,student_id,reg_date) VALUES (?,?,?)",
                              (aid, sid, (today - timedelta(days=25)).isoformat() + " 10:00:00"))
            if aid <= 3:  # กิจกรรมที่ผ่านไปแล้ว มีผลเช็คชื่อ
                st = random.choices(["present", "late", "absent", "excused"], [70, 12, 12, 6])[0]
                h = hours[aid] if st in ("present", "late") else 0
                sc = random.randint(7, 10) if h else 0
                con.execute("""INSERT INTO attendance(reg_id,check_in_time,attend_status,score,hours_earned)
                               VALUES (?,?,?,?,?)""",
                            (cur.lastrowid, "08:15" if h else None, st, sc, h))
    # บัญชีผู้ใช้
    pw = generate_password_hash
    con.execute("INSERT INTO user_account(username,password,role_id) VALUES (?,?,1)", ("admin", pw("admin123")))
    for tid in range(1, 5):
        con.execute("INSERT INTO user_account(username,password,role_id,teacher_id) VALUES (?,?,2,?)",
                    (f"teacher{tid}", pw("teacher123"), tid))
    for sid in range(1, 16):
        con.execute("INSERT INTO user_account(username,password,role_id,student_id) VALUES (?,?,3,?)",
                    (f"student{sid}", pw("student123"), sid))


# ---------------------------------------------------------------- auth
@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = q("""SELECT u.*, r.role_name,
                      COALESCE(s.first_name||' '||s.last_name, t.teacher_name, 'ผู้ดูแลระบบ') AS display_name
                      FROM user_account u JOIN role r USING(role_id)
                      LEFT JOIN student s USING(student_id) LEFT JOIN teacher t USING(teacher_id)
                      WHERE u.user_id=?""", (uid,), one=True)


def login_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if roles and g.user["role_name"] not in roles:
                flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "err")
                return redirect(url_for("dashboard"))
            return fn(*a, **kw)
        return wrapper
    return deco


def can_manage(activity_id):
    if g.user["role_name"] == "admin":
        return True
    if g.user["role_name"] == "teacher":
        return bool(q("SELECT 1 FROM activity_teacher WHERE activity_id=? AND teacher_id=?",
                      (activity_id, g.user["teacher_id"]), one=True))
    return False


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM user_account WHERE username=?", (request.form["username"].strip(),), one=True)
        if u and check_password_hash(u["password"], request.form["password"]):
            session["uid"] = u["user_id"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "err")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------- dashboard
def stats():
    one = lambda s, a=(): q(s, a, one=True)[0]
    data = {
        "activities": one("SELECT COUNT(*) FROM activity"),
        "students": one("SELECT COUNT(*) FROM student"),
        "registrations": one("SELECT COUNT(*) FROM registration WHERE reg_status='registered'"),
        "checkins": one("SELECT COUNT(*) FROM attendance WHERE attend_status IN ('present','late')"),
        "total_hours": one("SELECT COALESCE(SUM(hours_earned),0) FROM attendance"),
    }
    data["recent"] = [dict(r) for r in q("""
        SELECT s.first_name||' '||s.last_name AS student, a.activity_name, t.attend_status,
               t.check_in_time, t.hours_earned
        FROM attendance t JOIN registration r USING(reg_id)
        JOIN student s USING(student_id) JOIN activity a USING(activity_id)
        ORDER BY t.attendance_id DESC LIMIT 8""")]
    return data


@app.route("/dashboard")
@login_required()
def dashboard():
    up = q("""SELECT a.*, ty.type_name,
              (SELECT COUNT(*) FROM registration r WHERE r.activity_id=a.activity_id
               AND r.reg_status='registered') AS joined
              FROM activity a JOIN activity_type ty USING(type_id)
              WHERE activity_date >= date('now','localtime') ORDER BY activity_date LIMIT 5""")
    tot = mine = None
    if g.user["role_name"] == "student":
        sid = g.user["student_id"]
        tot = q("""SELECT COALESCE(SUM(t.hours_earned),0) h, COALESCE(SUM(t.score),0) sc,
                   COUNT(CASE WHEN t.attend_status IN ('present','late') THEN 1 END) n
                   FROM registration r JOIN attendance t USING(reg_id) WHERE r.student_id=?""",
                (sid,), one=True)
        mine = q("""SELECT a.activity_id, a.activity_name, a.activity_date, a.start_time, a.location
                    FROM registration r JOIN activity a USING(activity_id)
                    WHERE r.student_id=? AND r.reg_status='registered'
                    AND a.activity_date >= date('now','localtime') ORDER BY a.activity_date""", (sid,))
    return render_template("dashboard.html", s=stats(), upcoming=up, tot=tot, mine=mine)


@app.route("/api/stats")
@login_required()
def api_stats():
    return jsonify(stats())


# ---------------------------------------------------------------- activities
ACT_SQL = """SELECT a.*, ty.type_name, y.year_name, y.semester,
             (SELECT COUNT(*) FROM registration r WHERE r.activity_id=a.activity_id
              AND r.reg_status='registered') AS joined
             FROM activity a JOIN activity_type ty USING(type_id) JOIN academic_year y USING(year_id)"""


@app.route("/activities")
@login_required()
def activities():
    type_id = request.args.get("type", "")
    kw = request.args.get("q", "").strip()
    sql, args = ACT_SQL + " WHERE 1=1", []
    if type_id:
        sql += " AND a.type_id=?"; args.append(type_id)
    if kw:
        sql += " AND a.activity_name LIKE ?"; args.append(f"%{kw}%")
    rows = q(sql + " ORDER BY a.activity_date DESC", args)
    mine = set()
    if g.user["role_name"] == "student":
        mine = {r["activity_id"] for r in q(
            "SELECT activity_id FROM registration WHERE student_id=? AND reg_status='registered'",
            (g.user["student_id"],))}
    types = q("SELECT * FROM activity_type ORDER BY type_name")
    return render_template("activities.html", rows=rows, mine=mine, types=types,
                           type_id=type_id, kw=kw, today=date.today().isoformat())


def activity_form_data():
    f = request.form
    return (f["activity_name"].strip(), f["type_id"], f["year_id"], f["location"].strip(),
            f["activity_date"], f["start_time"], f["end_time"],
            int(f["max_participants"] or 0), float(f["hours"] or 0))


@app.route("/activities/new", methods=["GET", "POST"])
@login_required("admin", "teacher")
def activity_new():
    if request.method == "POST":
        cur = run("""INSERT INTO activity(activity_name,type_id,year_id,location,activity_date,
                     start_time,end_time,max_participants,hours) VALUES (?,?,?,?,?,?,?,?,?)""",
                  activity_form_data())
        if g.user["role_name"] == "teacher":  # ครูที่สร้าง ได้เป็นผู้ดูแลอัตโนมัติ
            run("INSERT INTO activity_teacher VALUES (?,?,?)",
                (cur.lastrowid, g.user["teacher_id"], "หัวหน้าฝ่าย"))
        flash("เพิ่มกิจกรรมเรียบร้อย", "ok")
        return redirect(url_for("activity_detail", aid=cur.lastrowid))
    return render_template("activity_form.html", a=None, **form_lists())


def form_lists():
    return dict(types=q("SELECT * FROM activity_type ORDER BY type_name"),
                years=q("SELECT * FROM academic_year ORDER BY year_name DESC, semester DESC"))


@app.route("/activities/<int:aid>/edit", methods=["GET", "POST"])
@login_required("admin", "teacher")
def activity_edit(aid):
    if not can_manage(aid):
        flash("แก้ไขได้เฉพาะกิจกรรมที่คุณเป็นครูผู้ดูแล", "err")
        return redirect(url_for("activities"))
    if request.method == "POST":
        run("""UPDATE activity SET activity_name=?,type_id=?,year_id=?,location=?,activity_date=?,
               start_time=?,end_time=?,max_participants=?,hours=? WHERE activity_id=?""",
            activity_form_data() + (aid,))
        flash("บันทึกการแก้ไขแล้ว", "ok")
        return redirect(url_for("activity_detail", aid=aid))
    a = q("SELECT * FROM activity WHERE activity_id=?", (aid,), one=True)
    return render_template("activity_form.html", a=a, **form_lists())


@app.post("/activities/<int:aid>/delete")
@login_required("admin", "teacher")
def activity_delete(aid):
    if can_manage(aid):
        run("DELETE FROM activity WHERE activity_id=?", (aid,))
        flash("ลบกิจกรรมแล้ว", "ok")
    return redirect(url_for("activities"))


@app.route("/activities/<int:aid>")
@login_required()
def activity_detail(aid):
    a = q(ACT_SQL + " WHERE a.activity_id=?", (aid,), one=True)
    if not a:
        return redirect(url_for("activities"))
    teachers = q("""SELECT t.*, at.duty FROM activity_teacher at JOIN teacher t USING(teacher_id)
                    WHERE at.activity_id=?""", (aid,))
    people = q("""SELECT r.reg_id, r.reg_date, s.student_id, s.first_name, s.last_name, s.grade, s.room,
                  t.check_in_time, t.attend_status, t.score, t.hours_earned, t.comment
                  FROM registration r JOIN student s USING(student_id)
                  LEFT JOIN attendance t USING(reg_id)
                  WHERE r.activity_id=? AND r.reg_status='registered' ORDER BY s.grade, s.room, s.first_name""",
               (aid,))
    all_teachers = q("SELECT * FROM teacher ORDER BY teacher_name")
    my_reg = None
    if g.user["role_name"] == "student":
        my_reg = q("SELECT * FROM registration WHERE activity_id=? AND student_id=?",
                   (aid, g.user["student_id"]), one=True)
    return render_template("activity_detail.html", a=a, teachers=teachers, people=people,
                           all_teachers=all_teachers, manage=can_manage(aid), my_reg=my_reg)


# ---- ครูผู้ดูแลกิจกรรม
@app.post("/activities/<int:aid>/teachers")
@login_required("admin", "teacher")
def activity_teacher_add(aid):
    if can_manage(aid):
        run("INSERT OR REPLACE INTO activity_teacher VALUES (?,?,?)",
            (aid, request.form["teacher_id"], request.form["duty"].strip()))
        flash("บันทึกครูผู้ดูแลแล้ว", "ok")
    return redirect(url_for("activity_detail", aid=aid))


@app.post("/activities/<int:aid>/teachers/<int:tid>/remove")
@login_required("admin", "teacher")
def activity_teacher_remove(aid, tid):
    if can_manage(aid):
        run("DELETE FROM activity_teacher WHERE activity_id=? AND teacher_id=?", (aid, tid))
    return redirect(url_for("activity_detail", aid=aid))


# ---- นักเรียนลงทะเบียน / ยกเลิก
@app.post("/activities/<int:aid>/register")
@login_required("student")
def register(aid):
    a = q(ACT_SQL + " WHERE a.activity_id=?", (aid,), one=True)
    sid = g.user["student_id"]
    old = q("SELECT * FROM registration WHERE activity_id=? AND student_id=?", (aid, sid), one=True)
    if a["activity_date"] < date.today().isoformat():
        flash("กิจกรรมนี้สิ้นสุดแล้ว", "err")
    elif old and old["reg_status"] == "registered":
        flash("คุณลงทะเบียนกิจกรรมนี้แล้ว", "err")
    elif a["joined"] >= a["max_participants"]:
        flash("กิจกรรมเต็มแล้ว", "err")
    else:
        if old:
            run("UPDATE registration SET reg_status='registered', reg_date=datetime('now','localtime') "
                "WHERE reg_id=?", (old["reg_id"],))
        else:
            run("INSERT INTO registration(activity_id,student_id) VALUES (?,?)", (aid, sid))
        flash("ลงทะเบียนสำเร็จ", "ok")
    return redirect(request.referrer or url_for("activities"))


@app.post("/activities/<int:aid>/cancel")
@login_required("student")
def cancel(aid):
    run("""UPDATE registration SET reg_status='cancelled'
           WHERE activity_id=? AND student_id=? AND NOT EXISTS
           (SELECT 1 FROM attendance t WHERE t.reg_id=registration.reg_id)""",
        (aid, g.user["student_id"]))
    flash("ยกเลิกการลงทะเบียนแล้ว (กิจกรรมที่เช็คชื่อแล้วจะยกเลิกไม่ได้)", "ok")
    return redirect(request.referrer or url_for("my_history"))


# ---- บันทึกผล: เช็คชื่อ / คะแนน / ชั่วโมง
def save_attendance(reg_id, status, score, hours, comment, checkin=None):
    act = q("""SELECT a.hours FROM registration r JOIN activity a USING(activity_id)
               WHERE r.reg_id=?""", (reg_id,), one=True)
    if hours in (None, ""):  # คำนวณชั่วโมงอัตโนมัติ
        hours = act["hours"] if status in ("present", "late") else 0
    cur = q("SELECT * FROM attendance WHERE reg_id=?", (reg_id,), one=True)
    if checkin is None:
        checkin = cur["check_in_time"] if cur else None
        if status in ("present", "late") and not checkin:
            checkin = datetime.now().strftime("%H:%M")
        if status in ("absent", "excused"):
            checkin = None
    if cur:
        run("""UPDATE attendance SET check_in_time=?,attend_status=?,score=?,hours_earned=?,comment=?
               WHERE reg_id=?""", (checkin, status, score, hours, comment, reg_id))
    else:
        run("""INSERT INTO attendance(reg_id,check_in_time,attend_status,score,hours_earned,comment)
               VALUES (?,?,?,?,?,?)""", (reg_id, checkin, status, score, hours, comment))


@app.post("/activities/<int:aid>/attendance")
@login_required("admin", "teacher")
def attendance_save(aid):
    if not can_manage(aid):
        flash("ไม่มีสิทธิ์บันทึกผลกิจกรรมนี้", "err")
        return redirect(url_for("activity_detail", aid=aid))
    for r in q("SELECT reg_id FROM registration WHERE activity_id=? AND reg_status='registered'", (aid,)):
        k = str(r["reg_id"])
        if f"status_{k}" in request.form:
            save_attendance(r["reg_id"], request.form[f"status_{k}"],
                            float(request.form.get(f"score_{k}") or 0),
                            request.form.get(f"hours_{k}"), request.form.get(f"comment_{k}", "").strip())
    flash("บันทึกผลการเข้าร่วมเรียบร้อย", "ok")
    return redirect(url_for("activity_detail", aid=aid))


@app.post("/activities/<int:aid>/checkin/<int:reg_id>")
@login_required("admin", "teacher")
def quick_checkin(aid, reg_id):
    if can_manage(aid):
        old = q("SELECT * FROM attendance WHERE reg_id=?", (reg_id,), one=True)
        save_attendance(reg_id, "present", old["score"] if old else 0, None, old["comment"] if old else "")
    return redirect(url_for("activity_detail", aid=aid))


# ---------------------------------------------------------------- student history
@app.route("/my")
@login_required("student")
def my_history():
    sid = g.user["student_id"]
    me = q("SELECT * FROM student WHERE student_id=?", (sid,), one=True)
    rows = q("""SELECT a.activity_id, a.activity_name, a.activity_date, ty.type_name, a.hours AS full_hours,
                r.reg_status, r.reg_date, t.attend_status, t.score, t.hours_earned, t.check_in_time
                FROM registration r JOIN activity a USING(activity_id) JOIN activity_type ty USING(type_id)
                LEFT JOIN attendance t USING(reg_id)
                WHERE r.student_id=? ORDER BY a.activity_date DESC""", (sid,))
    tot = q("""SELECT COALESCE(SUM(t.hours_earned),0) h, COALESCE(SUM(t.score),0) sc,
               COUNT(CASE WHEN t.attend_status IN ('present','late') THEN 1 END) n
               FROM registration r JOIN attendance t USING(reg_id) WHERE r.student_id=?""", (sid,), one=True)
    return render_template("my.html", me=me, rows=rows, tot=tot)


# ---------------------------------------------------------------- reports
@app.route("/reports/activities")
@login_required("admin", "teacher")
def report_activities():
    rows = q("""SELECT a.activity_id, a.activity_name, ty.type_name, a.activity_date, a.max_participants,
                COUNT(r.reg_id) AS registered,
                COALESCE(SUM(t.attend_status='present'),0) AS present,
                COALESCE(SUM(t.attend_status='late'),0) AS late,
                COALESCE(SUM(t.attend_status='absent'),0) AS absent,
                COALESCE(SUM(t.attend_status='excused'),0) AS excused,
                COALESCE(SUM(t.hours_earned),0) AS hours
                FROM activity a JOIN activity_type ty USING(type_id)
                LEFT JOIN registration r ON r.activity_id=a.activity_id AND r.reg_status='registered'
                LEFT JOIN attendance t ON t.reg_id=r.reg_id
                GROUP BY a.activity_id ORDER BY a.activity_date DESC""")
    bytype = q("""SELECT ty.type_name, COUNT(DISTINCT a.activity_id) AS acts, COUNT(r.reg_id) AS regs
                  FROM activity_type ty LEFT JOIN activity a USING(type_id)
                  LEFT JOIN registration r ON r.activity_id=a.activity_id AND r.reg_status='registered'
                  GROUP BY ty.type_id ORDER BY regs DESC""")
    return render_template("report_activities.html", rows=rows, bytype=bytype)


@app.route("/reports/students")
@login_required("admin", "teacher")
def report_students():
    grade = request.args.get("grade", "")
    sql = """SELECT s.student_id, s.first_name, s.last_name, s.grade, s.room,
             COUNT(CASE WHEN t.attend_status IN ('present','late') THEN 1 END) AS joined,
             COALESCE(SUM(t.hours_earned),0) AS hours, COALESCE(SUM(t.score),0) AS score
             FROM student s LEFT JOIN registration r ON r.student_id=s.student_id AND r.reg_status='registered'
             LEFT JOIN attendance t ON t.reg_id=r.reg_id"""
    args = []
    if grade:
        sql += " WHERE s.grade=?"; args.append(grade)
    rows = q(sql + " GROUP BY s.student_id ORDER BY hours DESC, score DESC", args)
    grades = q("SELECT DISTINCT grade FROM student ORDER BY grade")
    return render_template("report_students.html", rows=rows, grades=grades, grade=grade)


# ---------------------------------------------------------------- admin
MASTER = {
    "types": dict(title="ประเภทกิจกรรม", table="activity_type", pk="type_id",
                  fields=[("type_name", "ชื่อประเภท", "text")]),
    "years": dict(title="ปีการศึกษา", table="academic_year", pk="year_id",
                  fields=[("year_name", "ปีการศึกษา", "text"), ("semester", "ภาคเรียน", "number")]),
    "teachers": dict(title="ครู", table="teacher", pk="teacher_id",
                     fields=[("teacher_name", "ชื่อครู", "text"), ("department", "หมวดวิชา", "text"),
                             ("phone", "โทรศัพท์", "text")]),
    "students": dict(title="นักเรียน", table="student", pk="student_id",
                     fields=[("first_name", "ชื่อ", "text"), ("last_name", "นามสกุล", "text"),
                             ("grade", "ชั้น", "text"), ("room", "ห้อง", "text")]),
}


@app.route("/admin/<kind>", methods=["GET", "POST"])
@login_required("admin")
def master(kind):
    m = MASTER.get(kind)
    if not m:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        cols = [f[0] for f in m["fields"]]
        vals = [request.form[c].strip() for c in cols]
        pk = request.form.get("pk")
        try:
            if pk:
                run(f"UPDATE {m['table']} SET " + ",".join(f"{c}=?" for c in cols) +
                    f" WHERE {m['pk']}=?", vals + [pk])
            else:
                run(f"INSERT INTO {m['table']}({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals)
            flash("บันทึกแล้ว", "ok")
        except sqlite3.DatabaseError as e:
            flash(f"บันทึกไม่ได้: {e}", "err")
        return redirect(url_for("master", kind=kind))
    rows = q(f"SELECT * FROM {m['table']} ORDER BY {m['pk']}")
    edit = None
    if request.args.get("edit"):
        edit = q(f"SELECT * FROM {m['table']} WHERE {m['pk']}=?", (request.args["edit"],), one=True)
    return render_template("master.html", m=m, kind=kind, rows=rows, edit=edit)


@app.post("/admin/<kind>/<int:pk>/delete")
@login_required("admin")
def master_delete(kind, pk):
    m = MASTER.get(kind)
    if m:
        try:
            run(f"DELETE FROM {m['table']} WHERE {m['pk']}=?", (pk,))
            flash("ลบแล้ว", "ok")
        except sqlite3.IntegrityError:
            flash("ลบไม่ได้ เพราะมีข้อมูลอื่นอ้างอิงอยู่", "err")
    return redirect(url_for("master", kind=kind))


@app.route("/admin/users", methods=["GET", "POST"])
@login_required("admin")
def users():
    if request.method == "POST":
        f = request.form
        role = q("SELECT role_name FROM role WHERE role_id=?", (f["role_id"],), one=True)["role_name"]
        sid = f.get("student_id") or None if role == "student" else None
        tid = f.get("teacher_id") or None if role == "teacher" else None
        try:
            run("INSERT INTO user_account(username,password,role_id,student_id,teacher_id) VALUES (?,?,?,?,?)",
                (f["username"].strip(), generate_password_hash(f["password"]), f["role_id"], sid, tid))
            flash("สร้างบัญชีแล้ว", "ok")
        except sqlite3.IntegrityError:
            flash("สร้างไม่ได้: ชื่อผู้ใช้ซ้ำ หรือนักเรียน/ครูคนนี้มีบัญชีแล้ว", "err")
        return redirect(url_for("users"))
    rows = q("""SELECT u.user_id, u.username, r.role_name,
                COALESCE(s.first_name||' '||s.last_name, t.teacher_name, '-') AS owner
                FROM user_account u JOIN role r USING(role_id)
                LEFT JOIN student s USING(student_id) LEFT JOIN teacher t USING(teacher_id)
                ORDER BY r.role_id, u.user_id""")
    return render_template("users.html", rows=rows, roles=q("SELECT * FROM role"),
                           students=q("SELECT * FROM student ORDER BY first_name"),
                           teachers=q("SELECT * FROM teacher ORDER BY teacher_name"))


@app.post("/admin/users/<int:uid>/delete")
@login_required("admin")
def user_delete(uid):
    if uid == g.user["user_id"]:
        flash("ลบบัญชีที่กำลังใช้งานอยู่ไม่ได้", "err")
    else:
        run("DELETE FROM user_account WHERE user_id=?", (uid,))
        flash("ลบบัญชีแล้ว", "ok")
    return redirect(url_for("users"))


@app.post("/admin/users/<int:uid>/reset")
@login_required("admin")
def user_reset(uid):
    run("UPDATE user_account SET password=? WHERE user_id=?",
        (generate_password_hash(request.form["password"]), uid))
    flash("รีเซ็ตรหัสผ่านแล้ว", "ok")
    return redirect(url_for("users"))


@app.route("/er")
@login_required()
def er():
    return render_template("er.html")


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
        print("สร้างฐานข้อมูล sams.db พร้อมข้อมูลตัวอย่างแล้ว")
    app.run(debug=True, port=5000)
