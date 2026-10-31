struct Pair { a: u64, b: u64 }

fn main() {
    const N: u64 = 32_000_000;
    const RING: usize = 1024;
    let mut ring: Vec<Option<Box<Pair>>> = (0..RING).map(|_| None).collect();
    let mut sum: u64 = 0;
    for i in 0..N {
        let p = Box::new(Pair { a: i, b: i % 7 });
        let slot = &mut ring[(i % RING as u64) as usize];
        if let Some(old) = slot { sum += old.a + old.b; }
        *slot = Some(p);
    }
    for slot in ring.iter_mut() {
        if let Some(old) = slot.take() { sum += old.a + old.b; }
    }
    println!("{}", sum);
}
