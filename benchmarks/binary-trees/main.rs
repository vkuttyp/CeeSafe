struct Node { left: Option<Box<Node>>, right: Option<Box<Node>> }

fn make(depth: u32) -> Box<Node> {
    if depth == 0 { Box::new(Node { left: None, right: None }) }
    else { Box::new(Node { left: Some(make(depth - 1)), right: Some(make(depth - 1)) }) }
}

fn check(n: &Node) -> u64 {
    match (&n.left, &n.right) {
        (Some(l), Some(r)) => 1 + check(l) + check(r),
        _ => 1,
    }
}

fn main() {
    const MAX: u32 = 17;
    const MIN: u32 = 4;
    let mut total = check(&make(MAX + 1));
    let lived = make(MAX);
    let mut d = MIN;
    while d <= MAX {
        let iterations = 1u64 << (MAX - d + MIN);
        for _ in 0..iterations { total += check(&make(d)); }
        d += 2;
    }
    total += check(&lived);
    println!("{}", total);
}
