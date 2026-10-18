/**
 * @file sensor_cmd.c
 * @brief
 *
 * Copyright (c) 2020 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/******************************************************************************/
/* Includes                                                                   */
/******************************************************************************/
#include <string.h>

#include "sensor_cmd.h"

/******************************************************************************/
/* Local Constant, Macro and Type Definitions                                 */
/******************************************************************************/
static const char *ATTRIBUTES_THAT_REQUIRE_RESET[] = {
	"sensorName", "advertisingInterval", "advertisingDuration",
	"passkey",    "activeMode",	     "useCodedPhy"
};

/******************************************************************************/
/* Global Data Definitions                                                    */
/******************************************************************************/
const char SENSOR_CMD_SET_PREFIX[] =
	"{\"jsonrpc\":\"2.0\",\"id\":0,\"method\":\"set\",\"params\":";

const char SENSOR_CMD_SUFFIX[] = "}";

const char SENSOR_CMD_DUMP[] =
	"{\"jsonrpc\":\"2.0\",\"method\":\"dump\",\"id\":1}";

const char SENSOR_CMD_REBOOT[] =
	"{\"jsonrpc\": \"2.0\",\"method\":\"reboot\",\"id\":2}";

const char SENSOR_CMD_ACCEPTED_SUB_STR[] = "\"result\":\"ok\"";

const char SENSOR_CMD_DEFAULT_QUERY[] =
	"{\"jsonrpc\":\"2.0\",\"method\":\"get\",\"id\":4,\"params\":[\"sensorName\",\"location\",\"advertisingInterval\",\"advertisingDuration\",\"connectionTimeout\",\"passkey\",\"lock\",\"batterySenseInterval\",\"temperatureAggregationCount\",\"temperatureSenseInterval\",\"highTemperatureAlarmThreshold1\",\"highTemperatureAlarmThreshold2\",\"lowTemperatureAlarmThreshold1\",\"lowTemperatureAlarmThreshold2\",\"deltaTemperatureAlarmTheshold\",\"odr\",\"scale\",\"activationThreshold\",\"returnToSleepDuration\",\"tempCc\",\"batteryVoltageMv\",\"magnetState\",\"highTemperatureAlarm\",\"lowTemperatureAlarm\",\"deltaTemperatureAlarm\",\"movementAlarm\",\"hwVersion\",\"firmwareVersion\",\"resetReason\",\"bluetoothAddress\",\"activeMode\",\"flags\",\"resetCount\",\"useCodedPhy\",\"txPower\",\"networkId\",\"configVersion\",\"bootloaderVersion\"]}";

/* Defaults pushed once to a sensor whose configVersion is 0 (factory state).
 * Tuned for a 20-minute temperature cadence on a coin cell:
 *  - advertisingDuration 15000 / advertisingInterval 1000: 15 adverts per event,
 *    then the radio sleeps.  Duration 0 (or the old 1800000 factory value) makes
 *    the sensor advertise its last event for ever, which dominates the battery
 *    budget and is what Ezurio warns against below freezing.
 *  - odr 0 powers the LIS2DH accelerometer down.  The gateway never publishes
 *    movement events (only temperature/battery/reset), so a 100 Hz accelerometer
 *    was ~10-20 uA of pure waste; activationThreshold is parked at its max too.
 *  - batterySenseInterval 21600: one battery event (+ advert burst) per 6 h
 *    instead of hourly.  The power-fail circuit still raises batteryBad on its own.
 * Sensors already at configVersion 1 are NOT touched by this string; they need a
 * per-sensor shadow desired write with a higher configVersion.
 */
const char SENSOR_CMD_SET_CONFIG_VERSION_1[] =
	"{\"jsonrpc\":\"2.0\",\"method\":\"set\",\"id\":5,\"params\":{\"activeMode\":1,\"advertisingDuration\":15000,\"advertisingInterval\":1000,\"scale\":2,\"odr\":0,\"activationThreshold\":127,\"temperatureSenseInterval\":1200,\"batterySenseInterval\":21600,\"configVersion\":1}}";

const char SENSOR_CMD_SET_EPOCH_FMT_STR[] =
	"{\"jsonrpc\":\"2.0\",\"method\":\"setEpoch\",\"params\":[%u],\"id\":6}";

/******************************************************************************/
/* Global Function Definitions                                                */
/******************************************************************************/

bool SensorCmd_RequiresReset(char *pCmd)
{
	size_t i;
	for (i = 0; i < ARRAY_SIZE(ATTRIBUTES_THAT_REQUIRE_RESET); i++) {
		if (strstr(pCmd, ATTRIBUTES_THAT_REQUIRE_RESET[i]) != NULL) {
			return true;
		}
	}
	return false;
}
