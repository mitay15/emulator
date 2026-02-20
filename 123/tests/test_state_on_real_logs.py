import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from parser.timeline import TimelineBuilder
from parser.timeline_state import TimelineStateBuilder

print("=== Loading logs ===")
tb = TimelineBuilder("data")
events = tb.build_timeline()

print("Loaded events:", len(events))

print("=== Building states ===")
tsb = TimelineStateBuilder(events)
states = tsb.build()

print("Built states:", len(states))

# Покажем первые 5 состояний
for ts, st in states[:5]:
    print("\nTS:", ts)
    print("  BG:", st.glucose)
    print("  IOB:", st.iob)
    print("  COB:", st.cob)
    print("  autosens:", st.autosens)
    print("  autoISF:", st.autoisf)
    print("  target:", st.temp_target)
    print("  basal:", st.basal_profile)
    print("  temp basal:", st.temp_basal)
    print("  settings:", st.settings)
    print("  predictions:", st.predictions)

print("\n=== CycleInput test ===")

# Берём первый state
first_ts, first_state = states[0]

# Преобразуем в CycleInput
ci = first_state.to_cycle_input()

# Печатаем CycleInput
from pprint import pprint
pprint(ci.__dict__)


# Теперь можно вызывать движок
from emulator.determine_basal import DetermineBasalEngine
engine = DetermineBasalEngine()
result = engine.compute_from_input(ci)

print("\n=== Engine result ===")
print(result)
