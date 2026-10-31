fn main() {
    let mut sum: u64 = 0;
    for round in 0..10u64 {
        let mut v: Vec<u64> = Vec::new();
        for i in 0..20_000_000u64 { v.push((i + round) % 1000); }
        sum += v.iter().sum::<u64>();
    }
    println!("{}", sum);
}
