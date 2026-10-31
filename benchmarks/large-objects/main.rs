fn main() {
    const N: u64 = 400_000;
    const RING: usize = 8;
    const SIZE: usize = 65536;
    let mut ring: Vec<Option<Box<[u8; SIZE]>>> = (0..RING).map(|_| None).collect();
    let mut sum: u64 = 0;
    for i in 0..N {
        let mut b = Box::new([0u8; SIZE]);
        b[0] = (i % 256) as u8;
        b[SIZE - 1] = (3 * i % 256) as u8;
        let slot = &mut ring[(i % RING as u64) as usize];
        if let Some(old) = slot { sum += old[0] as u64 + old[SIZE - 1] as u64; }
        *slot = Some(b);
    }
    for slot in ring.iter_mut() {
        if let Some(old) = slot.take() { sum += old[0] as u64 + old[SIZE - 1] as u64; }
    }
    println!("{}", sum);
}
