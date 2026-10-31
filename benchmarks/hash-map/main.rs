const BITS: u32 = 22;
const MASK: u64 = (1 << BITS) - 1;
const N: u64 = 2_000_000;

fn slot_of(key: u64) -> usize { ((key * 2654435761 >> 10) & MASK) as usize }

fn find(keys: &[u64], key: u64) -> usize {
    let mut s = slot_of(key);
    while keys[s] != 0 && keys[s] != key { s = (s + 1) & MASK as usize; }
    s
}

fn main() {
    let mut keys = vec![0u64; (MASK + 1) as usize];
    let mut values = vec![0u64; (MASK + 1) as usize];
    for i in 0..N {
        let key = 7 * i + 1;
        let s = find(&keys, key);
        keys[s] = key;
        values[s] = i;
    }
    let (mut sum, mut misses) = (0u64, 0u64);
    for _ in 0..8 {
        for i in 0..N {
            for key in [7 * i + 1, 7 * i + 3] {
                let s = find(&keys, key);
                if keys[s] == key { sum += values[s]; } else { misses += 1; }
            }
        }
    }
    println!("{}", sum + misses);
}
