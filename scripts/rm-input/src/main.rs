// rm-input: uinput finger injector for reMarkable 2 (Type-B MT).
//
// Runs from /tmp over the existing SSH session. No tablet install, no
// Python, no daemon: one shot per invocation, device destroyed on exit.
// Event pattern mirrors references/03-input-automation.md §5 (ABS+SYN
// frames, BTN_TOUCH advertised, fresh tracking id per contact).
use std::os::unix::io::RawFd;
use std::path::Path;
use std::process::exit;
use std::env;
use std::ffi::CString;
use std::mem::zeroed;

const EV_SYN: u16 = 0x00;
const EV_KEY: u16 = 0x01;
const EV_ABS: u16 = 0x03;
const SYN_REPORT: u16 = 0;
const BTN_TOUCH: u16 = 0x14a;
const ABS_MT_SLOT: u16 = 0x2f;
const ABS_MT_TRACKING_ID: u16 = 0x39;
const ABS_MT_POSITION_X: u16 = 0x35;
const ABS_MT_POSITION_Y: u16 = 0x36;
const ABS_MT_PRESSURE: u16 = 0x3a;
const ABS_MT_TOUCH_MAJOR: u16 = 0x30;
const ABS_MT_TOUCH_MINOR: u16 = 0x31;
const ABS_MT_TOOL_TYPE: u16 = 0x37;
const ABS_MT_ORIENTATION: u16 = 0x34;
const MT_TOOL_FINGER: i32 = 0;
const TOUCH_SIZE: i32 = 40;
const PROP_DIRECT: u32 = 1;

const UI_SET_EVBIT: u64 = 0x40045564;
const UI_SET_KEYBIT: u64 = 0x40045565;
const UI_SET_ABSBIT: u64 = 0x40045567;
const UI_SET_PROPBIT: u64 = 0x4004556e;
const UI_DEV_SETUP: u64 = 0x405c5503;
const UI_DEV_CREATE: u64 = 0x5501;
const UI_DEV_DESTROY: u64 = 0x5502;
const EVIOCGNAME: u64 = 0x81004506;
const fn eviocgabs(axis: u16) -> u64 {
    0x80184500 + (0x40 + axis as u64)
}

const PRESSURE: i32 = 60;
const TAP_TID: i32 = 42;
const SWIPE_TID: i32 = 43;
const FALLBACK_X_MAX: i32 = 1403;
const FALLBACK_Y_MAX: i32 = 1871;
// Verbatim replay of the owner's finger double-swipe, device coords +
// relative ms. Captured 2026-09-18 on pt_mt; the pair took Notebook 19
// from 3 pages to 4. TRKIDs remapped to fresh values (601/602).
const REPLAY: &[(u64, u16, u16, i32)] = &[
    (0,3,57,601),
    (0,3,53,893),
    (0,3,54,519),
    (0,3,58,98),
    (0,0,0,0),
    (9,3,53,886),
    (0,3,54,520),
    (0,3,58,96),
    (0,0,0,0),
    (9,3,53,872),
    (0,3,54,523),
    (0,3,58,95),
    (0,3,49,8),
    (0,3,52,1),
    (0,0,0,0),
    (10,3,53,854),
    (0,3,54,526),
    (0,3,58,93),
    (0,3,49,17),
    (0,3,52,2),
    (0,0,0,0),
    (12,3,53,829),
    (0,3,54,530),
    (0,3,58,101),
    (0,0,0,0),
    (12,3,53,789),
    (0,3,54,535),
    (0,3,58,108),
    (0,3,48,17),
    (0,3,52,4),
    (0,0,0,0),
    (12,3,53,733),
    (0,3,54,541),
    (0,3,58,114),
    (0,0,0,0),
    (12,3,53,675),
    (0,3,54,545),
    (0,3,58,112),
    (0,3,49,8),
    (0,3,52,2),
    (0,0,0,0),
    (12,3,53,608),
    (0,3,54,547),
    (0,3,58,109),
    (0,3,49,17),
    (0,3,52,4),
    (0,0,0,0),
    (12,3,53,548),
    (0,3,54,548),
    (0,3,58,105),
    (0,0,0,0),
    (12,3,53,491),
    (0,3,58,95),
    (0,3,52,3),
    (0,0,0,0),
    (12,3,53,440),
    (0,3,54,545),
    (0,3,58,94),
    (0,3,48,8),
    (0,3,52,2),
    (0,0,0,0),
    (35,3,57,-1),
    (0,0,0,0),
    (2529,3,57,602),
    (0,3,53,981),
    (0,3,54,310),
    (0,3,58,69),
    (0,3,49,8),
    (0,3,52,1),
    (0,0,0,0),
    (17,3,53,979),
    (0,3,58,92),
    (0,3,49,17),
    (0,3,52,2),
    (0,0,0,0),
    (10,3,53,975),
    (0,0,0,0),
    (12,3,53,969),
    (0,3,54,312),
    (0,3,58,94),
    (0,0,0,0),
    (12,3,53,961),
    (0,3,54,314),
    (0,3,58,97),
    (0,0,0,0),
    (12,3,53,950),
    (0,3,54,317),
    (0,0,0,0),
    (12,3,53,936),
    (0,3,54,319),
    (0,3,58,100),
    (0,0,0,0),
    (12,3,53,920),
    (0,3,54,323),
    (0,3,58,103),
    (0,0,0,0),
    (12,3,53,901),
    (0,3,54,326),
    (0,3,58,105),
    (0,3,48,17),
    (0,3,52,3),
    (0,0,0,0),
    (12,3,53,879),
    (0,3,54,330),
    (0,3,58,104),
    (0,0,0,0),
    (12,3,53,854),
    (0,3,54,333),
    (0,3,58,106),
    (0,3,49,8),
    (0,3,52,2),
    (0,0,0,0),
    (12,3,53,825),
    (0,3,54,337),
    (0,3,58,113),
    (0,3,49,17),
    (0,3,52,3),
    (0,0,0,0),
    (12,3,53,791),
    (0,3,54,340),
    (0,3,58,111),
    (0,3,52,4),
    (0,0,0,0),
    (12,3,53,751),
    (0,3,54,343),
    (0,3,58,114),
    (0,0,0,0),
    (12,3,53,710),
    (0,3,54,345),
    (0,3,58,112),
    (0,3,49,8),
    (0,3,52,2),
    (0,0,0,0),
    (12,3,53,671),
    (0,3,54,347),
    (0,3,58,111),
    (0,0,0,0),
    (12,3,53,630),
    (0,3,54,349),
    (0,3,58,108),
    (0,3,49,17),
    (0,3,52,4),
    (0,0,0,0),
    (12,3,53,590),
    (0,3,54,350),
    (0,3,58,103),
    (0,0,0,0),
    (12,3,53,551),
    (0,3,54,351),
    (0,3,58,90),
    (0,3,52,3),
    (0,0,0,0),
    (36,3,57,-1),
    (0,0,0,0),
];

#[repr(C)]
struct UinputSetup {
    bustype: u16,
    vendor: u16,
    product: u16,
    version: u16,
    name: [u8; 80],
    ff_effects_max: u32,
}

#[repr(C)]
struct AbsInfo {
    value: i32,
    minimum: i32,
    maximum: i32,
    fuzz: i32,
    flat: i32,
    resolution: i32,
}

fn die(msg: &str) -> ! {
    eprintln!("rm-input: {}", msg);
    exit(1);
}

fn ioctl(fd: RawFd, req: u64, arg: *mut libc::c_void) -> bool {
    unsafe { libc::ioctl(fd, req as i32, arg) == 0 }
}

// Name/length ioctls return byte counts (>= 0), not 0.
fn ioctl_len(fd: RawFd, req: u64, arg: *mut libc::c_void) -> bool {
    unsafe { libc::ioctl(fd, req as i32, arg) >= 0 }
}

fn open(path: &str, flags: i32) -> RawFd {
    let c = CString::new(path).unwrap();
    unsafe { libc::open(c.as_ptr(), flags) }
}

// Never hardcodes event numbers: finds the finger node by name.
fn find_pt_mt() -> (String, AbsInfo, AbsInfo) {
    for n in 0..32 {
        let path = format!("/dev/input/event{}", n);
        let fd = open(&path, libc::O_RDONLY | libc::O_NONBLOCK);
        if fd < 0 {
            continue;
        }
        let mut name = [0u8; 256];
        let ok = ioctl_len(fd, EVIOCGNAME, name.as_mut_ptr() as *mut _)
            && name
                .split(|&b| b == 0)
                .next()
                .map(|s| s == b"pt_mt")
                .unwrap_or(false);
        if !ok {
            unsafe { libc::close(fd) };
            continue;
        }
        let mut x: AbsInfo = unsafe { zeroed() };
        let mut y: AbsInfo = unsafe { zeroed() };
        let qx = ioctl(fd, eviocgabs(ABS_MT_POSITION_X), &mut x as *mut _ as *mut _);
        let qy = ioctl(fd, eviocgabs(ABS_MT_POSITION_Y), &mut y as *mut _ as *mut _);
        unsafe { libc::close(fd) };
        if qx && qy && x.maximum > 0 && y.maximum > 0 {
            return (path, x, y);
        }
        // Ranges unreadable: fail loudly, never guess silently.
        die("pt_mt ranges unreadable via EVIOCGABS");
    }
    die("finger node pt_mt not found under /dev/input");
}

// Dumps EV/KEY/ABS bitmaps + absinfo for every set axis. Read-only.
fn dump_caps() {
    for n in 0..32 {
        let path = format!("/dev/input/event{}", n);
        let fd = open(&path, libc::O_RDONLY | libc::O_NONBLOCK);
        if fd < 0 {
            continue;
        }
        let mut name = [0u8; 256];
        if !ioctl_len(fd, EVIOCGNAME, name.as_mut_ptr() as *mut _) {
            unsafe { libc::close(fd) };
            continue;
        }
        let nm: String = name.split(|&b| b == 0).next()
            .map(|s| String::from_utf8_lossy(s).into_owned()).unwrap_or_default();
        const fn eviocgbit(ev: u16, len: u64) -> u64 {
            0x80000000 + (len << 16) + (0x45 << 8) + (0x20 + ev as u64)
        }
        let mut evb = [0u32; 1];
        let mut key = [0u32; 24];
        let mut abs = [0u32; 8];
        if !ioctl_len(fd, eviocgbit(0, 4), evb.as_mut_ptr() as *mut _) {
            unsafe { libc::close(fd) };
            continue;
        }
        ioctl_len(fd, eviocgbit(1, 96), key.as_mut_ptr() as *mut _);
        ioctl_len(fd, eviocgbit(3, 32), abs.as_mut_ptr() as *mut _);
        println!("{} {} ev={:08x}", path, nm, evb[0]);
        print!("  key:");
        for (i, w) in key.iter().enumerate() {
            if *w != 0 {
                print!(" [{}]={:08x}", i, w);
            }
        }
        println!();
        print!("  abs:");
        for (i, w) in abs.iter().enumerate() {
            if *w != 0 {
                print!(" [{}]={:08x}", i, w);
            }
        }
        println!();
        for axis in 0..64u16 {
            if abs[(axis / 32) as usize] & (1 << (axis % 32)) != 0 {
                let mut info: AbsInfo = unsafe { zeroed() };
                if ioctl(fd, eviocgabs(axis), &mut info as *mut _ as *mut _) {
                    println!("  absinfo {:02x}: val={} min={} max={} fuzz={} flat={} res={}",
                        axis, info.value, info.minimum, info.maximum,
                        info.fuzz, info.flat, info.resolution);
                }
            }
        }
        unsafe { libc::close(fd) };
    }
}

fn emit(fd: RawFd, ty: u16, code: u16, value: i32) {
    let mut tv: libc::timeval = unsafe { zeroed() };
    unsafe { libc::gettimeofday(&mut tv, std::ptr::null_mut()) };
    #[repr(C)]
    struct Ev {
        tv: libc::timeval,
        ty: u16,
        code: u16,
        value: i32,
    }
    let ev = Ev { tv, ty, code, value };
    let p = &ev as *const Ev as *const u8;
    let buf = unsafe { std::slice::from_raw_parts(p, std::mem::size_of::<Ev>()) };
    let mut off = 0;
    while off < buf.len() {
        let n = unsafe { libc::write(fd, buf[off..].as_ptr() as *const _, (buf.len() - off) as usize) };
        if n <= 0 {
            die("short write to /dev/uinput");
        }
        off += n as usize;
    }
}

fn sync(fd: RawFd) {
    emit(fd, EV_SYN, SYN_REPORT, 0);
}

fn msleep(ms: u64) {
    let ts = libc::timespec {
        tv_sec: (ms / 1000) as libc::time_t,
        tv_nsec: ((ms % 1000) * 1_000_000) as _,
    };
    unsafe { libc::nanosleep(&ts, std::ptr::null_mut()) };
}

fn set_bit(fd: RawFd, req: u64, bit: u32, what: &str) {
    if !ioctl(fd, req, bit as *mut libc::c_void) {
        die(what);
    }
}

// Creates the virtual finger device; returns its fd. Destroyed by caller.
fn create_device(x_max: i32, y_max: i32) -> RawFd {
    let fd = open("/dev/uinput", libc::O_WRONLY | libc::O_NONBLOCK);
    if fd < 0 {
        die("cannot open /dev/uinput");
    }
    set_bit(fd, UI_SET_EVBIT, EV_SYN as u32, "UI_SET_EVBIT/SYN");
    set_bit(fd, UI_SET_EVBIT, EV_KEY as u32, "UI_SET_EVBIT/KEY");
    set_bit(fd, UI_SET_EVBIT, EV_ABS as u32, "UI_SET_EVBIT/ABS");
    set_bit(fd, UI_SET_KEYBIT, BTN_TOUCH as u32, "UI_SET_KEYBIT/TOUCH");
    for b in [ABS_MT_SLOT, ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_PRESSURE, ABS_MT_TOUCH_MAJOR, ABS_MT_TOUCH_MINOR, ABS_MT_TOOL_TYPE, ABS_MT_ORIENTATION] {
        set_bit(fd, UI_SET_ABSBIT, b as u32, "UI_SET_ABSBIT");
    }
    set_bit(fd, UI_SET_PROPBIT, PROP_DIRECT, "UI_SET_PROPBIT/DIRECT");
    let mut setup: UinputSetup = unsafe { zeroed() };
    setup.bustype = 0x03; // BUS_USB, matches python-evdev UInput default
    let name = b"rm2-touch-inject";
    setup.name[..name.len()].copy_from_slice(name);
    if !ioctl(fd, UI_DEV_SETUP, &mut setup as *mut _ as *mut _) {
        unsafe { libc::close(fd) };
        die("UI_DEV_SETUP failed");
    }
    #[repr(C)]
    struct AbsSetup {
        code: u16,
        pad: u16,
        info: AbsInfo,
    }
    const UI_ABS_SETUP: u64 = 0x401c5504;
    for (code, min, max) in [(ABS_MT_SLOT, 0, 31), (ABS_MT_TRACKING_ID, 0, 65535), (ABS_MT_POSITION_X, 0, x_max), (ABS_MT_POSITION_Y, 0, y_max), (ABS_MT_PRESSURE, 0, 255), (ABS_MT_TOUCH_MAJOR, 0, 255), (ABS_MT_TOUCH_MINOR, 0, 255), (ABS_MT_TOOL_TYPE, 0, 1), (ABS_MT_ORIENTATION, -127, 127)] {
        let mut s = AbsSetup {
            code,
            pad: 0,
            info: AbsInfo { value: 0, minimum: min, maximum: max, fuzz: 0, flat: 0, resolution: 0 },
        };
        if !ioctl(fd, UI_ABS_SETUP, &mut s as *mut _ as *mut _) {
            unsafe { libc::close(fd) };
            die("UI_ABS_SETUP failed");
        }
    }
    if !ioctl(fd, UI_DEV_CREATE, std::ptr::null_mut()) {
        unsafe { libc::close(fd) };
        die("UI_DEV_CREATE failed");
    }
    msleep(1000); // hotplug discovery (Qt inotify rescan) must see the node before first event
    fd
}

fn destroy(fd: RawFd) {
    msleep(500); // let handlers consume the lift before the node vanishes
    ioctl(fd, UI_DEV_DESTROY, std::ptr::null_mut());
    unsafe { libc::close(fd) };
}

fn clamp(v: i32, lo: i32, hi: i32, what: &str) -> i32 {
    if v < lo || v > hi {
        die(&format!("{}={} outside [{}..{}]", what, v, lo, hi));
    }
    v
}

fn parse(args: &[String], i: usize, what: &str) -> i32 {
    args.get(i)
        .and_then(|s| s.parse::<i32>().ok())
        .unwrap_or_else(|| die(&format!("bad {}", what)))
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() >= 2 && args[1] == "--probe" {
        dump_caps();
        let u = Path::new("/dev/uinput").exists();
        let (node, x, y) = find_pt_mt();
        println!("node={} x=[{}..{}] y=[{}..{}] uinput={}",
            node, x.minimum, x.maximum, y.minimum, y.maximum,
            if u { "present" } else { "MISSING" });
        if !u {
            exit(2);
        }
        return;
    }
    if args.len() >= 4 && args[1] == "tap" {
        let (node, x, y) = find_pt_mt();
        let _ = node;
        let xmax = if x.maximum > 0 && x.maximum <= 4096 { x.maximum } else { FALLBACK_X_MAX };
        let ymax = if y.maximum > 0 && y.maximum <= 4096 { y.maximum } else { FALLBACK_Y_MAX };
        // Screen coords in, device coords out: touch Y is flipped
        // (proven live: raw (57,61) lands at screen bottom-left).
        let px = clamp(parse(&args, 2, "X"), x.minimum, xmax, "X");
        let py = ymax + y.minimum - clamp(parse(&args, 3, "Y"), y.minimum, ymax, "Y");
        let fd = create_device(xmax, ymax);
        emit(fd, EV_ABS, ABS_MT_SLOT, 0);
        emit(fd, EV_ABS, ABS_MT_TRACKING_ID, TAP_TID);
        emit(fd, EV_ABS, ABS_MT_POSITION_X, px);
        emit(fd, EV_ABS, ABS_MT_POSITION_Y, py);
        emit(fd, EV_ABS, ABS_MT_PRESSURE, PRESSURE);
        emit(fd, EV_ABS, ABS_MT_TOUCH_MAJOR, TOUCH_SIZE);
        emit(fd, EV_ABS, ABS_MT_TOUCH_MINOR, TOUCH_SIZE);
        emit(fd, EV_ABS, ABS_MT_TOOL_TYPE, MT_TOOL_FINGER);
        sync(fd);
        emit(fd, EV_ABS, ABS_MT_TRACKING_ID, -1);
        sync(fd);
        destroy(fd);
        println!("ok tap {} {}", px, py);
        return;
    }
    if args.len() >= 6 && args[1] == "swipe" {
        let (node, x, y) = find_pt_mt();
        let _ = node;
        let xmax = if x.maximum > 0 && x.maximum <= 4096 { x.maximum } else { FALLBACK_X_MAX };
        let ymax = if y.maximum > 0 && y.maximum <= 4096 { y.maximum } else { FALLBACK_Y_MAX };
        let x1 = clamp(parse(&args, 2, "X1"), x.minimum, xmax, "X1");
        let y1 = ymax + y.minimum - clamp(parse(&args, 3, "Y1"), y.minimum, ymax, "Y1");
        let x2 = clamp(parse(&args, 4, "X2"), x.minimum, xmax, "X2");
        let y2 = ymax + y.minimum - clamp(parse(&args, 5, "Y2"), y.minimum, ymax, "Y2");
        let steps = if args.len() > 6 { parse(&args, 6, "STEPS") } else { 24 };
        let step_ms = if args.len() > 7 { parse(&args, 7, "STEP_MS") as u64 } else { 12 };
        if steps < 1 || steps > 200 || step_ms > 5000 {
            die("STEPS 1..200, STEP_MS <= 5000");
        }
        let fd = create_device(xmax, ymax);
        emit(fd, EV_ABS, ABS_MT_SLOT, 0);
        emit(fd, EV_ABS, ABS_MT_TRACKING_ID, SWIPE_TID);
        for i in 0..=steps {
            emit(fd, EV_ABS, ABS_MT_POSITION_X, x1 + (x2 - x1) * i / steps);
            emit(fd, EV_ABS, ABS_MT_POSITION_Y, y1 + (y2 - y1) * i / steps);
            emit(fd, EV_ABS, ABS_MT_PRESSURE, PRESSURE);
            // Finger-sized contact (ablation 2026-09-18: MAJOR/MINOR 40
            // is palm-rejected in doc view 0/2; sparse 8/17 creates.
            // Pressure/orientation/tool-type/path-shape all irrelevant.)
            let sz = if (i / 3) % 2 == 0 { 8 } else { 17 };
            if i % 3 == 0 {
                emit(fd, EV_ABS, ABS_MT_TOUCH_MAJOR, sz);
            }
            emit(fd, EV_ABS, ABS_MT_TOUCH_MINOR, sz);
            emit(fd, EV_ABS, ABS_MT_TOOL_TYPE, MT_TOOL_FINGER);
            sync(fd);
            if i < steps {
                msleep(step_ms);
            }
        }
        emit(fd, EV_ABS, ABS_MT_TRACKING_ID, -1);
        sync(fd);
        destroy(fd);
        println!("ok swipe {} {} {} {} steps={}", x1, y1, x2, y2, steps);
        return;
    }
    if args.len() >= 2 && args[1] == "replay" {
        let (node, x, y) = find_pt_mt();
        let _ = node;
        let xmax = if x.maximum > 0 && x.maximum <= 4096 { x.maximum } else { FALLBACK_X_MAX };
        let ymax = if y.maximum > 0 && y.maximum <= 4096 { y.maximum } else { FALLBACK_Y_MAX };
        let _ = (xmax, ymax);
        // Optional variant file: lines of "dt_ms type code value".
        // No arg = baked-in owner finger pair (device coords).
        let table: Vec<(u64, u16, u16, i32)> = if args.len() >= 3 {
            let txt = std::fs::read_to_string(&args[2]).unwrap_or_else(|_| die("cannot read replay file"));
            let mut v = Vec::new();
            for (li, ln) in txt.lines().enumerate() {
                let ln = ln.trim();
                if ln.is_empty() || ln.starts_with('#') {
                    continue;
                }
                let p: Vec<&str> = ln.split_whitespace().collect();
                if p.len() != 4 {
                    die(&format!("replay line {}: want 4 ints", li + 1));
                }
                let dt: u64 = p[0].parse().unwrap_or_else(|_| die("bad dt"));
                let ty: u16 = p[1].parse().unwrap_or_else(|_| die("bad type"));
                let code: u16 = p[2].parse().unwrap_or_else(|_| die("bad code"));
                let val: i32 = p[3].parse().unwrap_or_else(|_| die("bad value"));
                v.push((dt, ty, code, val));
            }
            if v.is_empty() {
                die("replay file empty");
            }
            v
        } else {
            REPLAY.to_vec()
        };
        let fd = create_device(xmax, ymax);
        for &(dt, ty, code, val) in &table {
            if dt > 0 {
                msleep(dt);
            }
            if ty == EV_SYN {
                sync(fd);
            } else {
                emit(fd, ty, code, val);
            }
        }
        destroy(fd);
        println!("ok replay {} events", table.len());
        return;
    }
    eprintln!("usage: rm-input --probe | tap X Y | swipe X1 Y1 X2 Y2 [STEPS=24] [STEP_MS=12] | replay");
    eprintln!("coords are SCREEN pixels (1404x1872 portrait); Y flip applied internally; replay is device coords");
    exit(2);
}
