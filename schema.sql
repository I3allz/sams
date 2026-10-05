-- SAMS : School Activity Management System (3NF, 10 ตาราง ตามรายงาน)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS academic_year (
    year_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    year_name TEXT NOT NULL,
    semester  INTEGER NOT NULL CHECK (semester IN (1,2,3))
);

CREATE TABLE IF NOT EXISTS activity_type (
    type_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS activity (
    activity_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_name    TEXT NOT NULL,
    type_id          INTEGER NOT NULL REFERENCES activity_type(type_id),
    year_id          INTEGER NOT NULL REFERENCES academic_year(year_id),
    location         TEXT,
    activity_date    TEXT NOT NULL,
    start_time       TEXT,
    end_time         TEXT,
    max_participants INTEGER NOT NULL DEFAULT 50,
    hours            REAL NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS teacher (
    teacher_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_name TEXT NOT NULL,
    department   TEXT,
    phone        TEXT
);

CREATE TABLE IF NOT EXISTS activity_teacher (
    activity_id INTEGER NOT NULL REFERENCES activity(activity_id) ON DELETE CASCADE,
    teacher_id  INTEGER NOT NULL REFERENCES teacher(teacher_id),
    duty        TEXT,
    PRIMARY KEY (activity_id, teacher_id)
);

CREATE TABLE IF NOT EXISTS student (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    grade      TEXT,
    room       TEXT
);

CREATE TABLE IF NOT EXISTS registration (
    reg_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activity(activity_id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES student(student_id),
    reg_date    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    reg_status  TEXT NOT NULL DEFAULT 'registered' CHECK (reg_status IN ('registered','cancelled')),
    UNIQUE (activity_id, student_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_id        INTEGER NOT NULL UNIQUE REFERENCES registration(reg_id) ON DELETE CASCADE,
    check_in_time TEXT,
    attend_status TEXT NOT NULL DEFAULT 'absent' CHECK (attend_status IN ('present','late','absent','excused')),
    score         REAL DEFAULT 0,
    hours_earned  REAL DEFAULT 0,
    comment       TEXT
);

CREATE TABLE IF NOT EXISTS role (
    role_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_account (
    user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    password   TEXT NOT NULL,
    role_id    INTEGER NOT NULL REFERENCES role(role_id),
    student_id INTEGER UNIQUE REFERENCES student(student_id),
    teacher_id INTEGER UNIQUE REFERENCES teacher(teacher_id)
);
