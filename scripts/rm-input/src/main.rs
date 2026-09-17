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
const BTN_TOOL_PEN: u16 = 0x140;
const BTN_TOOL_RUBBER: u16 = 0x141;
const BTN_STYLUS: u16 = 0x14b;
const BTN_STYLUS2: u16 = 0x14c;
const ABS_X: u16 = 0x00;
const ABS_Y: u16 = 0x01;
const ABS_PRESSURE: u16 = 0x18;
const ABS_DISTANCE: u16 = 0x19;
const ABS_TILT_X: u16 = 0x1a;
const ABS_TILT_Y: u16 = 0x1b;
// Wacom I2C Digitizer ranges, probed live 2026-09-18 via --probe.
const PEN_X_MAX: i32 = 20966;
const PEN_Y_MAX: i32 = 15725;
const PEN_PRESSURE_MAX: i32 = 4095;
#[repr(C)]
struct AbsSetup {
    code: u16,
    pad: u16,
    info: AbsInfo,
}
const UI_ABS_SETUP: u64 = 0x401c5504;

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
        #[repr(C)]
        struct InputId { bustype: u16, vendor: u16, product: u16, version: u16 }
        let mut id: InputId = unsafe { zeroed() };
        const EVIOCGID: u64 = 0x80084502;
        if ioctl_len(fd, EVIOCGID, &mut id as *mut _ as *mut _) {
            println!("  id: bus={:#06x} vendor={:#06x} product={:#06x} version={:#06x}",
                id.bustype, id.vendor, id.product, id.version);
        }
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

// Virtual pen cloning the Wacom I2C Digitizer caps (probed 2026-09-18).
fn create_pen_device() -> RawFd {
    let fd = open("/dev/uinput", libc::O_WRONLY | libc::O_NONBLOCK);
    if fd < 0 {
        die("cannot open /dev/uinput");
    }
    set_bit(fd, UI_SET_EVBIT, EV_SYN as u32, "UI_SET_EVBIT/SYN");
    set_bit(fd, UI_SET_EVBIT, EV_KEY as u32, "UI_SET_EVBIT/KEY");
    set_bit(fd, UI_SET_EVBIT, EV_ABS as u32, "UI_SET_EVBIT/ABS");
    for b in [BTN_TOOL_PEN, BTN_TOOL_RUBBER, BTN_TOUCH, BTN_STYLUS, BTN_STYLUS2] {
        set_bit(fd, UI_SET_KEYBIT, b as u32, "UI_SET_KEYBIT/pen");
    }
    for b in [ABS_X, ABS_Y, ABS_PRESSURE, ABS_DISTANCE, ABS_TILT_X, ABS_TILT_Y] {
        set_bit(fd, UI_SET_ABSBIT, b as u32, "UI_SET_ABSBIT/pen");
    }
    // Identity clones the real node (name + I2C bus + no props):
    // the generic rm2-pen-inject device drew nothing (blank canvas).
    let mut setup: UinputSetup = unsafe { zeroed() };
    setup.bustype = 0x18; // BUS_I2C, like the real Wacom node
    setup.vendor = 0x2d1f;
    setup.product = 0x0095;
    setup.version = 0x1231;
    let name = b"rm2-pen-inject";
    setup.name[..name.len()].copy_from_slice(name);
    if !ioctl(fd, UI_DEV_SETUP, &mut setup as *mut _ as *mut _) {
        unsafe { libc::close(fd) };
        die("UI_DEV_SETUP failed");
    }
    for (code, min, max, res) in [(ABS_X, 0, PEN_X_MAX, 100), (ABS_Y, 0, PEN_Y_MAX, 100), (ABS_PRESSURE, 0, PEN_PRESSURE_MAX, 0), (ABS_DISTANCE, 0, 255, 0), (ABS_TILT_X, -9000, 9000, 0), (ABS_TILT_Y, -9000, 9000, 0)] {
        let mut s = AbsSetup {
            code,
            pad: 0,
            info: AbsInfo { value: 0, minimum: min, maximum: max, fuzz: 0, flat: 0, resolution: res },
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
    msleep(1000);
    fd
}

// Screen (1404x1872 portrait) to digitizer mapping, hypothesis A:
// digitizer X = screen Y * k, digitizer Y = screen X * k,
// k = 20966/1872 = 15725/1404 = 11.199. Calibrate with penraw
// if ink lands mirrored.
fn map_pen(sx: i32, sy: i32) -> (i32, i32) {
    (((clamp(sy, 0, 1871, "Y") as f64) * 11.199) as i32,
     ((clamp(sx, 0, 1403, "X") as f64) * 11.199) as i32)
}

// One pen-down stroke in DEVICE coords. Hover first (proximity arms the
// tool), then contact with constant pressure, then a clean lift.
fn pen_stroke(fd: RawFd, x1: i32, y1: i32, x2: i32, y2: i32, steps: i32, step_ms: u64, press: i32) {
    emit(fd, EV_KEY, BTN_TOOL_PEN, 1);
    emit(fd, EV_ABS, ABS_X, x1);
    emit(fd, EV_ABS, ABS_Y, y1);
    emit(fd, EV_ABS, ABS_DISTANCE, 86);
    sync(fd);
    msleep(100);
    for i in 0..=steps {
        if i == 0 {
            // Touch joins the first contact frame with position+pressure,
            // never as a position-less frame of its own.
            emit(fd, EV_KEY, BTN_TOUCH, 1);
        }
        emit(fd, EV_ABS, ABS_X, x1 + (x2 - x1) * i / steps);
        emit(fd, EV_ABS, ABS_Y, y1 + (y2 - y1) * i / steps);
        emit(fd, EV_ABS, ABS_PRESSURE, press);
        emit(fd, EV_ABS, ABS_DISTANCE, 0);
        emit(fd, EV_ABS, ABS_TILT_X, 0);
        emit(fd, EV_ABS, ABS_TILT_Y, 0);
        sync(fd);
        if i < steps {
            msleep(step_ms);
        }
    }
    emit(fd, EV_ABS, ABS_PRESSURE, 0);
    emit(fd, EV_KEY, BTN_TOUCH, 0);
    emit(fd, EV_KEY, BTN_TOOL_PEN, 0);
    sync(fd);
}

// Multi-point stroke in DEVICE coords: one hover, one contact pass
// through every point, one lift. Steps split across segments
// proportional to segment length (min 1 step per segment).
fn pen_stroke_multi(fd: RawFd, pts: &[(i32, i32)], steps: i32, step_ms: u64, press: i32) {
    emit(fd, EV_KEY, BTN_TOOL_PEN, 1);
    emit(fd, EV_ABS, ABS_X, pts[0].0);
    emit(fd, EV_ABS, ABS_Y, pts[0].1);
    emit(fd, EV_ABS, ABS_DISTANCE, 86);
    sync(fd);
    msleep(100);
    // (no lone TOUCH frame: it joins the first contact frame below)
    let mut lens = Vec::new();
    let mut total: i64 = 0;
    for w in pts.windows(2) {
        let l = ((w[1].0 - w[0].0) as i64).abs() + ((w[1].1 - w[0].1) as i64).abs();
        lens.push(l);
        total += l;
    }
    for (si, w) in pts.windows(2).enumerate() {
        let n = if total > 0 {
            std::cmp::max(1, (lens[si] * steps as i64 / total) as i32)
        } else {
            1
        };
        for i in 0..=n {
            if si == 0 && i == 0 {
                emit(fd, EV_KEY, BTN_TOUCH, 1);
            }
            emit(fd, EV_ABS, ABS_X, w[0].0 + (w[1].0 - w[0].0) * i / n);
            emit(fd, EV_ABS, ABS_Y, w[0].1 + (w[1].1 - w[0].1) * i / n);
            emit(fd, EV_ABS, ABS_PRESSURE, press);
            emit(fd, EV_ABS, ABS_DISTANCE, 0);
            emit(fd, EV_ABS, ABS_TILT_X, 0);
            emit(fd, EV_ABS, ABS_TILT_Y, 0);
            sync(fd);
            msleep(step_ms);
        }
    }
    emit(fd, EV_ABS, ABS_PRESSURE, 0);
    emit(fd, EV_KEY, BTN_TOUCH, 0);
    emit(fd, EV_KEY, BTN_TOOL_PEN, 0);
    sync(fd);
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
    if args.len() >= 6 && (args[1] == "pen" || args[1] == "penraw") {
        let raw = args[1] == "penraw";
        // Screen coords (portrait 1404x1872) unless penraw (device coords).
        // Mapping hypothesis A: digitizer X = screen Y * k, digitizer Y
        // = screen X * k, k = 20966/1872 = 15725/1404 = 11.199.
        // Calibrate with penraw if ink lands mirrored.
        let (ax1, ay1, ax2, ay2) = (parse(&args, 2, "X1"), parse(&args, 3, "Y1"), parse(&args, 4, "X2"), parse(&args, 5, "Y2"));
        let steps = if args.len() > 6 { parse(&args, 6, "STEPS") } else { 24 };
        let step_ms = if args.len() > 7 { parse(&args, 7, "STEP_MS") as u64 } else { 12 };
        let press = if args.len() > 8 { parse(&args, 8, "PRESS") } else { 1500 };
        if steps < 1 || steps > 200 || step_ms > 5000 {
            die("STEPS 1..200, STEP_MS <= 5000");
        }
        let (dx1, dy1, dx2, dy2) = if raw {
            (clamp(ax1, 0, PEN_X_MAX, "DX1"), clamp(ay1, 0, PEN_Y_MAX, "DY1"),
             clamp(ax2, 0, PEN_X_MAX, "DX2"), clamp(ay2, 0, PEN_Y_MAX, "DY2"))
        } else {
            (((clamp(ay1, 0, 1871, "Y1") as f64) * 11.199) as i32,
             ((clamp(ax1, 0, 1403, "X1") as f64) * 11.199) as i32,
             ((clamp(ay2, 0, 1871, "Y2") as f64) * 11.199) as i32,
             ((clamp(ax2, 0, 1403, "X2") as f64) * 11.199) as i32)
        };
        let press = clamp(press, 1, PEN_PRESSURE_MAX, "PRESS");
        let fd = create_pen_device();
        pen_stroke(fd, dx1, dy1, dx2, dy2, steps, step_ms, press);
        destroy(fd);
        println!("ok pen {} {} -> {} {} steps={}", dx1, dy1, dx2, dy2, steps);
        return;
    }
    if args.len() >= 3 && args[1] == "penhold" {
        // Debug: create the pen device, keep it alive SEC seconds for
        // host-side --probe comparison against the real digitizer.
        let secs = parse(&args, 2, "SEC") as u64;
        let fd = create_pen_device();
        println!("holding pen device {}s", secs);
        msleep(secs * 1000);
        destroy(fd);
        println!("ok penhold");
        return;
    }

    if args.len() >= 9 && args[1] == "penpoly" {
        // penpoly STEPS STEP_MS PRESS X1 Y1 X2 Y2 [X3 Y3 ...]:
        // one pen-down pass through every point (screen coords).
        let steps = parse(&args, 2, "STEPS");
        let step_ms = parse(&args, 3, "STEP_MS") as u64;
        let press = clamp(parse(&args, 4, "PRESS"), 1, PEN_PRESSURE_MAX, "PRESS");
        if steps < 1 || steps > 2000 {
            die("STEPS 1..2000");
        }
        let rest = &args[5..];
        if rest.len() < 4 || rest.len() % 2 != 0 {
            die("penpoly needs >= 2 XY pairs");
        }
        let mut pts = Vec::new();
        for w in rest.chunks(2) {
            let sx: i32 = w[0].parse().unwrap_or_else(|_| die("bad X"));
            let sy: i32 = w[1].parse().unwrap_or_else(|_| die("bad Y"));
            pts.push(map_pen(sx, sy));
        }
        let fd = create_pen_device();
        pen_stroke_multi(fd, &pts, steps, step_ms, press);
        destroy(fd);
        println!("ok penpoly {} pts steps={}", pts.len(), steps);
        return;
    }

    eprintln!("usage: rm-input --probe | tap X Y | swipe X1 Y1 X2 Y2 [STEPS=24] [STEP_MS=12] | replay [FILE] | pen X1 Y1 X2 Y2 [STEPS=24] [STEP_MS=12] [PRESS=1500] | penraw DX1 DY1 DX2 DY2 ...");
    eprintln!("coords are SCREEN pixels (1404x1872 portrait); Y flip applied internally; replay is device coords");
    exit(2);
}
