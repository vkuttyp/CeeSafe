fn main() {
    const LIMIT: usize = 40_000_000;
    const M: usize = 320;
    let mut composite = vec![0u8; LIMIT + 1];
    let mut primes = 0u64;
    for i in 2..=LIMIT {
        if composite[i] != 0 { continue; }
        primes += 1;
        let mut j = i * i;
        while j <= LIMIT { composite[j] = 1; j += i; }
    }
    let mut a = vec![0u64; M * M];
    let mut b = vec![0u64; M * M];
    for i in 0..M { for j in 0..M { a[i * M + j] = (i * j % 100) as u64; b[i * M + j] = ((i + j) % 100) as u64; } }
    let mut product = 0u64;
    for i in 0..M {
        for j in 0..M {
            let mut c = 0u64;
            for k in 0..M { c += a[i * M + k] * b[k * M + j]; }
            product += c;
        }
    }
    println!("{}", primes * 1_000_000 + product % 1_000_000);
}
