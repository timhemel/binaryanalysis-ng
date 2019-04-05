
import pstats
import sys

p = pstats.Stats(sys.argv[1])
p.sort_stats("cumulative")
# p.sort_stats("filename")
p.print_stats()

p.print_callers()
p.print_callees()

