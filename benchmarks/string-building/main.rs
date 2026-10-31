fn main() {
    let mut total: u64 = 0;
    for round in 0..30u64 {
        let mut s = String::new();
        for i in 0..1_000_000u64 {
            let mut digits = [0u8; 20];
            let mut n = 0;
            let mut v = i + round;
            loop {
                digits[n] = b'0' + (v % 10) as u8;
                n += 1;
                v /= 10;
                if v == 0 { break; }
            }
            while n > 0 { n -= 1; s.push(digits[n] as char); }
            s.push(',');
        }
        let bytes: u64 = s.bytes().map(|b| b as u64).sum();
        total += s.len() as u64 * 1000 + bytes % 1000;
    }
    println!("{}", total);
}
