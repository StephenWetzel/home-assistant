from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("-f", "--force", help="Force deletions, do not ask", action="store_true")
parser.add_argument("-d", "--dry", help="Perform a dry run, do not delete any rows", action="store_true")
args = parser.parse_args()
if args.force:
    print("Forcing deletions")


engine = create_engine('sqlite:////home/homeassistant/.homeassistant/home-assistant_v2.db', echo=False)
Base = automap_base()
Base.prepare(engine, reflect=True)

State = Base.classes.states
Event = Base.classes.events

def scrub_table_unknowns(session, entity_id, state = 'unknown'):
    res = session.query(State).filter_by(state = state)
    print("Entity {} has {} rows with state '{}'".format(entity_id, res.count(), state))
    if res.count() < 1: return
    for row in res:
        print("Unknown: {}".format(row.state))
    ans = input("Do you want to delete these {} rows [y/N]? ".format(res.count()))
    if ans == 'y':
        res.delete(synchronize_session=False)
        session.commit()

def scrub_table(session, entity_id, offset = 10, min_rows = 100, padding = 5):
    scrub_table_unknowns(session, entity_id)
    res = session.query(State).filter_by(entity_id = entity_id)
    print("Entity {} has {} rows".format(entity_id, res.count()))
    if res.count() < min_rows:
        print("Not enough rows")
        return
    # The idea here is if you have thousands of data points and only one or two are off by a lot
    # An example of temperature data points: (30, 32, 62, 63, 64, ... 65, 66), where 30 and 32 are errors, and we want to delete them
    # We take the 10th lowest point, subtract 5, and call that the cut off.  For my data that works well, but you will want to think about your data.
    # There are better ways to do this with standard deviations or deltas between points, but this was simple and works well for me.
    low_cut_off = float(res.order_by(State.state)[offset].state) - padding
    high_cut_off = float(res.order_by(State.state)[-1 - offset].state) + padding
    print("Low cut off {}, high cut off {}".format(low_cut_off, high_cut_off))
    delete_count = 0
    for row in res.filter(State.state > high_cut_off):
        print("Too high: {}".format(row.state))
        delete_count += 1
    for row in res.filter(State.state < low_cut_off):
        print("Too low: {}".format(row.state))
        delete_count += 1
    if delete_count == 0: return
    if args.dry: return
    if args.force:
        res.filter(State.state > high_cut_off).delete(synchronize_session=False)
        res.filter(State.state < low_cut_off).delete(synchronize_session=False)
        session.commit()
        return
    ans = input("Do you want to delete these {} rows [y/N]? ".format(delete_count))
    if ans == 'y':
        res.filter(State.state > high_cut_off).delete(synchronize_session=False)
        res.filter(State.state < low_cut_off).delete(synchronize_session=False)
        session.commit()


if __name__ == "__main__":
    session = Session(engine)
    scrub_table(session, 'sensor.bedroom_temperature')
    scrub_table(session, 'sensor.bedroom_humidity')
    scrub_table(session, 'sensor.living_room_temperature')
    scrub_table(session, 'sensor.living_room_humidity')
    scrub_table(session, 'sensor.dht_sensor_humidity')
    scrub_table(session, 'sensor.dht_sensor_temperature')

