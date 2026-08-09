cql()
result 1-0
initial
line --> move to e4 --> move to d5

cql()
line --> check move previous capture d8 from Q to q 

// this is only move filters not position filters that is why it works if i mix them it won't work example ´move from B to h7 capture p check´ error
cql()
result 1-0
line --> move from B to h7 capture p
     --> move from k to h7 capture B
     --> move from N to g5


this works by seaarching positions [p0,p1,p3]
cql()
result 1-0
line --> move from B to p capture h7
     --> check
     --> move previous capture B
     --> move previous from N to g5


// this shows an example of how to mix capture and previous
cql()
result 1-0
line --> move from B to p capture h7
     --> check
     --> move previous from k to h7 capture B
     --> move previous from N to g5