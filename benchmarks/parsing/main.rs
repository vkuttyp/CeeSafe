fn number(b: &mut Vec<u8>, value: u64) {
    let mut digits = [0u8; 20];
    let mut n = 0;
    let mut v = value;
    loop {
        digits[n] = b'0' + (v % 10) as u8;
        n += 1;
        v /= 10;
        if v == 0 { break; }
    }
    while n > 0 { n -= 1; b.push(digits[n]); }
}

fn main() {
    let mut b: Vec<u8> = Vec::new();
    for i in 0..2_000_000u64 {
        b.push(b'k');
        number(&mut b, i);
        b.push(b'=');
        number(&mut b, 7 * i % 100000);
        b.push(b'\n');
    }
    let mut sum = 0u64;
    for _ in 0..8 {
        let mut i = 0;
        while i < b.len() {
            while b[i] != b'=' { i += 1; }
            i += 1;
            let mut v = 0u64;
            while b[i] != b'\n' { v = v * 10 + (b[i] - b'0') as u64; i += 1; }
            i += 1;
            sum += v;
        }
    }
    println!("{}", sum);
}
