const N: usize = 1_000_000;
const W: i32 = 1000;

fn step(p: &mut i32, v: &mut i32) {
    *p += *v;
    if *p < 0 { *p = -*p; *v = -*v; }
    else if *p >= W { *p = 2 * (W - 1) - *p; *v = -*v; }
}

fn main() {
    let mut x = vec![0i32; N];
    let mut y = vec![0i32; N];
    let mut vx = vec![0i32; N];
    let mut vy = vec![0i32; N];
    for i in 0..N {
        let k = i as i32;
        x[i] = k % 1000; y[i] = 3 * k % 1000; vx[i] = k % 7 - 3; vy[i] = k % 5 - 2;
    }
    for _ in 0..100 {
        for i in 0..N { step(&mut x[i], &mut vx[i]); step(&mut y[i], &mut vy[i]); }
    }
    let sum: u64 = (0..N).map(|i| (x[i] + y[i]) as u64).sum();
    println!("{}", sum);
}
