
import sys
import csv

buckets = {}

csv_reader = csv.DictReader(sys.stdin)
for r in csv_reader:
    unpacker = r['unpacker']
    result = r['result']
    time = int(r['time'])
    b = buckets.setdefault(unpacker, {'True': 0, 'False': 0, 'cTrue': 0, 'cFalse': 0})
    b[result] += time
    b['c'+result] += 1
    # print(buckets)

class PrettyWriter:

    def __init__(self,outf):
        self.outf = outf

    def writeseparator(self):
        print("-"* (20+5*2+12*2+10*2+6), file=self.outf)

    def writeheader(self):
        print("%-20s %5s %5s %12s %12s %10s %10s" % (
            "unpacker", "#pass", "#fail",
            "time-pass", "time-fail",
            "%pass", "%fail"), file=self.outf)

    def writerow(self,d):
        print("%(unpacker)-20s %(count_true)5d %(count_false)5d %(time_true)12d %(time_false)12d %(pct_true)10.2f %(pct_false)10.2f" % d, file=self.outf)
        pass

# writer = csv.DictWriter(sys.stdout,['unpacker','time_true','time_false'])


def update_total(tot,d):
    tot['time_true'] += d['time_true']
    tot['time_false'] += d['time_false']
    tot['count_true'] += d['count_true']
    tot['count_false'] += d['count_false']
    return tot

total = { 'time_true':0, 'time_false':0, 'count_true':0, 'count_false': 0 }

def sort_by_total_time(buckets):
    return (u for k,u in sorted(
        (
            (buckets[k]['True'] + buckets[k]['False'], k)
                for k in buckets
        ) , reverse = True )
    )

writer = PrettyWriter(sys.stdout)
writer.writeheader()
writer.writeseparator()

for k in sort_by_total_time(buckets):
    d = { 'unpacker' : k,
            'time_true' : buckets[k]['True'],
            'time_false' : buckets[k]['False'],
            'count_true' : buckets[k]['cTrue'],
            'count_false' : buckets[k]['cFalse'],
            'count_total' : buckets[k]['cTrue']+buckets[k]['cFalse'],
            'time_total' : buckets[k]['True']+buckets[k]['False'],
            'pct_true' : 100*buckets[k]['True'] / (buckets[k]['True']+buckets[k]['False']),
            'pct_false' : 100*buckets[k]['False'] / (buckets[k]['True']+buckets[k]['False']),
        }
    writer.writerow(d)
    total = update_total(total,d)

total['unpacker'] = 'total'
total['count_total'] = total['count_true']+total['count_false']
total['time_total'] = total['time_true']+total['time_false']
total['pct_true'] = 100*total['time_true'] / total['time_total']
total['pct_false'] = 100*total['time_false'] / total['time_total']

writer.writeseparator()
writer.writerow(total)
