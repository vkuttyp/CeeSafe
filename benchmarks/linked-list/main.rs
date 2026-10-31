struct Node { value: u64, next: Option<Box<Node>> }

fn main() {
    let mut sum = 0u64;
    for round in 0..10u64 {
        let mut head: Option<Box<Node>> = None;
        for i in 0..2_000_000u64 { head = Some(Box::new(Node { value: (i + round) % 1000, next: head })); }
        let mut at = head.as_deref();
        while let Some(n) = at { sum += n.value; at = n.next.as_deref(); }
        // Iterative: the default recursive drop would overflow the stack.
        while let Some(mut n) = head { head = n.next.take(); }
    }
    println!("{}", sum);
}
