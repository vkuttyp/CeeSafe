fn main() {
    let mut sum: u64 = 0;
    for i in 0..20_000_000u64 {
        let mut a = [0u64; 32];
        for j in 0..32 { a[j] = (i + j as u64) % 1000; }
        for x in a { sum += x; }
    }
    println!("{}", sum);
}
