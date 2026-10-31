fn main() {
    const SIZE: usize = 16 << 20;
    const BLOCK: usize = 4096;
    let src: Vec<u8> = (0..SIZE).map(|i| (i % 251) as u8).collect();
    let mut dst = vec![0u8; SIZE];
    let mut sum = 0u64;
    for _ in 0..320 {
        for i in 0..SIZE / BLOCK {
            let at = i * 2053 % (SIZE / BLOCK) * BLOCK;
            dst[at..at + BLOCK].copy_from_slice(&src[at..at + BLOCK]);
        }
        let mut at = 0;
        while at < SIZE { sum += dst[at] as u64; at += BLOCK; }
    }
    println!("{}", sum);
}
