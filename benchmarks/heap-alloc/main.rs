fn main() {
    let mut sum: u64 = 0;
    for i in 0..10_000_000u64 {
        let mut a = Box::new([0u64; 32]);
        for j in 0..32 { a[j] = (i + j as u64) % 1000; }
        for x in a.iter() { sum += x; }
    }
    println!("{}", sum);
}
