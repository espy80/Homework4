from collections import deque # double-ended queue
from numpy import random
import simpy
from simpy.util import start_delayed

# Hourly percentages of car traffic from national models
# Hourly rates begin with the midnight - 1:00 AM hour
hourlyRates = [0.0081, 0.0052, 0.0047, 0.0057, 0.0099, 0.0230, 0.0489, 0.0679, 0.0629, 0.0531, 0.0509, 0.0538, 0.0560, 0.0574, 0.0635, 0.0733, 0.0804, 0.0775, 0.0579, 0.0437, 0.0338, 0.0280, 0.0205, 0.0138]

# From the Omaha Traffic Count PDF
# 67th & Pacific 31,938 8,752 13,514 18,594 23,016 09/17
# 50th & Underwood Ave 12,816 4,856 4,432 7,270 9,074
eadt = 12816
# Numbers for NSEW are every car to pass through
# A car traveling North to South would get counted in each value.

north = 4856
south = 4432
east = 7270
west = 9074

# Intersection Configuration
EW_Lanes = 2
NS_Lanes = 2

EW_Green = 60
NS_Green = 45
green_direction = "EW"
# Control Device can be a "Light", "Sign", or "Roundabout"
# Stop signs cannot be used for intersections with more than 2 lanes
controlDevice = "Light"
departRate = 2 #how quickly can they go once it is their turn in seconds.
#Create an empty event log that will contain all the data for the simulation
eventLog = []

#Output file
outFile = "output.csv"

#Useful Constants
SECONDS_PER_HOUR = 60 * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24

# Lists of cars in a row from the various directions. Only used if there is a line.
eastCars = []
westCars = []
northCars = []
southCars = []

carCount = 0
departCount = 0
signOrder = []
roundBlocked = {"N":[],"S":[], "E":[], "W":[]}

# Simulation for the traffic light. For simplicity, yellow is ignored.
def traffic_light(env):
    """
    Toggles the green direction between East-West to North-South.
    """
    global green_direction
    while True:
        green_direction = "EW"
        yield env.timeout(EW_Green)
        green_direction = "NS"
        yield env.timeout(NS_Green)

def arrive(env, dir):
    """
    This function will place a new car at the intersection.
    Cars arrive at an equal rate based on the national averages per hour.
    """
    global carCount
    arrivalRate = 0

    while True:
        carCount += 1
        hour = int(env.now // SECONDS_PER_HOUR)
        logInfo = (carCount, env.now, dir)
        if len(signOrder) < 4:
            try:
                signOrder.index(dir)
            except Exception as e:
                signOrder.append(dir)
        if dir == "N":
            northCars.append(logInfo)
            arrivalRate = int(SECONDS_PER_HOUR / (north/2 * hourlyRates[hour])  + .5)
        if dir == "W":
            westCars.append(logInfo)
            arrivalRate = int(SECONDS_PER_HOUR / (west/2 * hourlyRates[hour])  + .5)
        if dir == "S":
            southCars.append(logInfo)
            arrivalRate = int(SECONDS_PER_HOUR / (south/2 * hourlyRates[hour]) + .5)
        if dir == "E":
            eastCars.append(logInfo)
            arrivalRate = int(SECONDS_PER_HOUR / (east/2 * hourlyRates[hour]) + .5)

        # determine delay time until the next car by the current hour
        yield env.timeout(arrivalRate)

def departSign(env):
    """
    Function that determines who is going to depart the stop sign.
    """
    while True:
        if len(signOrder) == 0:
            pass
        else:
            carDir = signOrder.pop(0)

            if carDir == "N":
                car = northCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                if len(northCars) > 0:
                    signOrder.append("N")
            if carDir == "W":
                car = westCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                if len(westCars) > 0:
                    signOrder.append("W")
            if carDir == "S":
                car = southCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                if len(southCars) > 0:
                    signOrder.append("S")
            if carDir == "E":
                car = eastCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                if len(eastCars) > 0:
                    signOrder.append("E")

        yield env.timeout(departRate)


def departRoundabout(env, dir):
    """
    Function that determines who is going to depart the roundabout.
    """
    while True:
        #check to see if you can go.
        #as a car enters, it will close off the lane to it's right for a (duration)
        while len(roundBlocked[dir]) > 0:
            #Roundabout is full, wait one time unit and check again.
            yield env.timeout(1)


        if dir == "N":
            if len(northCars) > 0:
                car = northCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                roundBlocked["W"].append(car[0]) #add self to blocked list.
                yield env.timeout(departRate)
                roundBlocked["W"].remove(car[0]) #remove self from blocked list.
            else:
                yield env.timeout(1)

        if dir == "W":
            if len(westCars) > 0:
                car = westCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                roundBlocked["S"].append(car[0]) #add self to blocked list.
                yield env.timeout(departRate)
                roundBlocked["S"].remove(car[0]) #remove self from blocked list.
            else:
                yield env.timeout(1)

        if dir == "S":
            if len(southCars) > 0:
                car = southCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                roundBlocked["E"].append(car[0]) #add self to blocked list.
                yield env.timeout(departRate)
                roundBlocked["E"].remove(car[0]) #remove self from blocked list.
            else:
                yield env.timeout(1)

        if dir == "E":
            if len(eastCars) > 0:
                car = eastCars.pop(0)
                eventLog.append((car[0], car[1], env.now, car[2]))
                roundBlocked["N"].append(car[0]) #add self to blocked list.
                yield env.timeout(departRate)
                roundBlocked["N"].remove(car[0]) #remove self from blocked list.
            else:
                yield env.timeout(1)



def departLight(env):
    """
    Function that determines who will depart from a stop light
    """
    while True:
        if green_direction == "EW":
            #deque the east and west cars if there are any in the queue
            for lane in range(EW_Lanes//2):
                if len(eastCars) > 0:
                    car = eastCars.pop(0)
                    eventLog.append((car[0], car[1], env.now, car[2]))
                if len(westCars) > 0:
                    car = westCars.pop(0)
                    eventLog.append((car[0], car[1], env.now, car[2]))

        elif green_direction == "NS":
            #deque the north and south cars if there are any in the queue
            for lane in range(NS_Lanes//2):
                if len(northCars) > 0:
                    car = northCars.pop(0)
                    eventLog.append((car[0], car[1], env.now, car[2]))
                if len(southCars) > 0:
                    car = southCars.pop(0)
                    eventLog.append((car[0], car[1], env.now, car[2]))

        yield env.timeout(departRate)




def main():

    control = controlDevice.lower()
    env = simpy.Environment()
    env.process(arrive(env, "N"))
    env.process(arrive(env, "S"))
    env.process(arrive(env, "E"))
    env.process(arrive(env, "W"))
    if control == "light":
        env.process(traffic_light(env))
        env.process(departLight(env))
    elif control == "sign":
        env.process(departSign(env))
    elif control == "roundabout":
        env.process(departRoundabout(env, "N"))
        env.process(departRoundabout(env, "S"))
        env.process(departRoundabout(env, "E"))
        env.process(departRoundabout(env, "W"))

    env.run(until=SECONDS_PER_DAY)

    print("Simulation complete")
    #print(eventLog)
    file = open(outFile, 'w')
    file.write("Car_Number,Arrive,Depart,Wait,Direction\n")
    for e in eventLog:
        carNum, arrival, departure, direction = e #unpack the tuple to multiple variables.
        waitTime = departure - arrival
        file.write(str(carNum) +"," + str(arrival) + "," + str(departure) + "," + str(waitTime) + "," + direction + "\n")

    file.close()

if __name__ == '__main__':
    main()
