/**
 * @file ess_sensor.c
 * @brief Connects to ESS (BL654 Sensor) and configures ESS service for
 * notifications.
 *
 * Copyright (c) 2020-2021 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <logging/log.h>
#define LOG_LEVEL LOG_LEVEL_DBG
LOG_MODULE_REGISTER(ess_sensor, CONFIG_ESS_SENSOR_LOG_LEVEL);

/******************************************************************************/
/* Includes                                                                   */
/******************************************************************************/
#include <zephyr.h>
#include <stddef.h>
#include <bluetooth/gatt.h>
#include <bluetooth/bluetooth.h>
#include <sys/byteorder.h>

#include "wdt.h"
#include "FrameworkIncludes.h"
#include "laird_utility_macros.h"
#include "lcz_bluetooth.h"
#include "led_configuration.h"
#include "ad_find.h"
#include "lcz_bt_scan.h"
#include "attr.h"

#ifdef CONFIG_SD_CARD_LOG
#include "sdcard_log.h"
#endif

/******************************************************************************/
/* Local Constant, Macro and Type Definitions                                 */
/******************************************************************************/
#define ESS_SENSOR_MIN_CONN_INTERVAL 80 /* in 1.25ms units, 80 = 100ms */
#define ESS_SENSOR_MAX_CONN_INTERVAL 160 /* in 1.25ms units, 160 = 200ms */
#define ESS_SENSOR_LATENCY 2
#define ESS_SENSOR_TIMEOUT 400 /* in 10ms units, 400 = 4s */
#define DISCOVER_SERVICES_DELAY_SECONDS 1

#ifdef HAS_SECOND_BLUETOOTH_LED
static const struct lcz_led_blink_pattern LED_SENSOR_SEARCH_PATTERN = {
	.on_time = CONFIG_DEFAULT_LED_ON_TIME_FOR_1_SECOND_BLINK,
	.off_time = CONFIG_DEFAULT_LED_OFF_TIME_FOR_1_SECOND_BLINK,
	.repeat_count = REPEAT_INDEFINITELY
};
#endif

struct remote_ble_sensor {
	/* State of app, see CENTRAL_STATE_XXX */
	uint8_t app_state;
	/* Handle of ESS service, used when searching for chars */
	uint16_t ess_service_handle;
	/* Temperature gatt subscribe parameters, see gatt.h for contents */
	struct bt_gatt_subscribe_params temperature_subscribe_params;
	/* Pressure gatt subscribe parameters, see gatt.h for contents */
	struct bt_gatt_subscribe_params pressure_subscribe_params;
	/* Humidity gatt subscribe parameters, see gatt.h for contents */
	struct bt_gatt_subscribe_params humidity_subscribe_params;
};

enum SENSOR_TYPES {
	SENSOR_TYPE_TEMPERATURE = 0,
	SENSOR_TYPE_HUMIDITY,
	SENSOR_TYPE_PRESSURE,
	SENSOR_TYPE_DEW_POINT,

	SENSOR_TYPE_MAX
};

/******************************************************************************/
/* Local Function Prototypes                                                  */
/******************************************************************************/
/* This callback is triggered when notifications from remote device are received */
static uint8_t notify_func_callback(struct bt_conn *conn,
				    struct bt_gatt_subscribe_params *params,
				    const void *data, uint16_t length);

/* This callback is triggered when remote services are discovered */
static uint8_t service_discover_func(struct bt_conn *conn,
				     const struct bt_gatt_attr *attr,
				     struct bt_gatt_discover_params *params);

/* This callback is triggered when remote characteristics are discovered */
static uint8_t char_discover_func(struct bt_conn *conn,
				  const struct bt_gatt_attr *attr,
				  struct bt_gatt_discover_params *params);

/* This callback is triggered when remote descriptors are discovered */
static uint8_t desc_discover_func(struct bt_conn *conn,
				  const struct bt_gatt_attr *attr,
				  struct bt_gatt_discover_params *params);

/* This callback is triggered when a BLE disconnection occurs */
static void disconnected(struct bt_conn *conn, uint8_t reason);

/* This callback is triggered when a BLE connection occurs */
static void connected(struct bt_conn *conn, uint8_t err);

/* This function is used to discover services in remote device */
static int find_service(struct bt_conn *conn, struct bt_uuid_16 n_uuid);

/* This function is used to discover characteristics in remote device */
static int find_char(struct bt_conn *conn, struct bt_uuid_16 n_uuid);

/* This function is used to discover descriptors in remote device */
static int find_desc(struct bt_conn *conn, struct bt_uuid_16 uuid,
		     uint16_t start_handle);

static void set_ble_state(enum central_state state);

static void discover_services_work_callback(struct k_work *work);
static void discover_failed_handler(struct bt_conn *conn, int err);

static void sensor_aggregator(uint8_t sensor, int32_t reading);

static bool process_device_uuid(struct bt_data *data);

static bool process_device_name(struct bt_data *data);

static bool process_device(struct bt_data *data, void *user_data);

static void ess_sensor_adv_handler(const bt_addr_le_t *addr, int8_t rssi,
				   uint8_t type, struct net_buf_simple *ad);

/******************************************************************************/
/* Local Data Definitions                                                     */
/******************************************************************************/
static struct bt_conn *sensor_conn = NULL;

static struct bt_uuid_16 uuid = BT_UUID_INIT_16(0);

static struct bt_gatt_discover_params discover_params;

static struct k_work_delayable discover_services_work;

static struct remote_ble_sensor remote;

static struct bt_conn_cb conn_callbacks = {
	.connected = connected,
	.disconnected = disconnected,
};

static float temperature;
static float humidity;
static float pressure;

static bool updated_temperature;
static bool updated_humidity;
static bool updated_pressure;

static int scan_id;

/* Store last searched UUID to prevent local out of scope variable access */
static struct bt_uuid_16 last_searched_uuid;

/******************************************************************************/
/* Global Function Definitions                                                */
/******************************************************************************/
void ess_sensor_initialize(void)
{
	k_work_init_delayable(&discover_services_work,
			      discover_services_work_callback);

	bt_conn_cb_register(&conn_callbacks);

	lcz_bt_scan_register(&scan_id, ess_sensor_adv_handler);

	set_ble_state(CENTRAL_STATE_FINDING_DEVICE);
}

int ess_sensor_disconnect(void)
{
	int r = 0;

	if (sensor_conn) {
		r = bt_conn_disconnect(sensor_conn,
				       BT_HCI_ERR_REMOTE_USER_TERM_CONN);
	}

	return r;
}

/******************************************************************************/
/* Local Function Definitions                                                 */
/******************************************************************************/
static bool process_device_uuid(struct bt_data *data)
{
	uint16_t uuid;
	uint8_t i = 0;

	while (i < data->data_len) {
		memcpy(&uuid, &data->data[i], sizeof(uuid));
		i += sizeof(uuid);

		if (sys_le16_to_cpu(uuid) == BT_UUID_ESS_VAL) {
			/* This is the ESS UUID we wanted */
			return true;
		}
	}

	/* ESS UUID not found */
	return false;
}

static bool process_device_name(struct bt_data *data)
{
	if (data->data_len == (sizeof(
		CONFIG_ESS_SENSOR_LEGACY_BL654_SENSOR_NAME) - 1)) {
		/* Size matches, compare name */
		if (memcmp(data->data, CONFIG_ESS_SENSOR_LEGACY_BL654_SENSOR_NAME,
		    (sizeof(
			CONFIG_ESS_SENSOR_LEGACY_BL654_SENSOR_NAME) - 1)) == 0) {
			/* Name matches, we have found our target device */
			return true;
		}
	}
	return false;
}

static bool process_device(struct bt_data *data, void *user_data)
{
	bt_addr_le_t *addr = user_data;
	char bt_addr[BT_ADDR_LE_STR_LEN];
	int err;
	bool ess_device = false;

	/* Check 16-bit UUIDs for ESS UUID and device name for legacy BL654
	 * sensor board
	 */
	if ((data->type == BT_DATA_UUID16_SOME || data->type ==
	     BT_DATA_UUID16_ALL) && (data->data_len % sizeof(uint16_t) == 0)) {
		ess_device = process_device_uuid(data);
	} else if ((data->type == BT_DATA_NAME_SHORTENED || data->type ==
		    BT_DATA_NAME_COMPLETE) && data->data_len > 1) {
		ess_device = process_device_name(data);
	}

	if (ess_device == true) {
		/* ESS UUID found! Can't connect while scanning */
		lcz_bt_scan_stop(scan_id);

		/* Connect to device */
		bt_addr_le_to_str(addr, bt_addr, sizeof(bt_addr));
		err = bt_conn_le_create(addr, BT_CONN_LE_CREATE_CONN,
					BT_LE_CONN_PARAM(
					ESS_SENSOR_MIN_CONN_INTERVAL,
					ESS_SENSOR_MAX_CONN_INTERVAL,
					ESS_SENSOR_LATENCY,
					ESS_SENSOR_TIMEOUT),
					&sensor_conn);

		if (err == 0) {
			LOG_INF("Attempting to connect to ESS device %s",
				log_strdup(bt_addr));
		} else {
			LOG_ERR("Failed to connect to ESS device %s err [%d]",
			log_strdup(bt_addr), err);
			set_ble_state(CENTRAL_STATE_FINDING_DEVICE);
		}

		return false;
	}

	return true;
}

static void ess_sensor_adv_handler(const bt_addr_le_t *addr, int8_t rssi,
				   uint8_t type, struct net_buf_simple *ad)
{
	/* If the ad is processed by multiple users, then it must be cloned
	 * because bt_data_parse modifies then net buf.
	 */
	struct net_buf_simple clone;

	/* Leave this function if already connected */
	if (sensor_conn) {
		return;
	}

	/* We're only interested in connectable events */
	if (type != BT_GAP_ADV_TYPE_ADV_IND &&
	    type != BT_GAP_ADV_TYPE_ADV_DIRECT_IND &&
	    type != BT_GAP_ADV_TYPE_SCAN_RSP) {
		return;
	}

	/* Process device services */
	net_buf_simple_clone(ad, &clone);
	bt_data_parse(&clone, process_device, (void *)addr);
}

static void discover_services_work_callback(struct k_work *work)
{
	ARG_UNUSED(work);
	if (sensor_conn) {
		memcpy(&uuid, BT_UUID_ESS, sizeof(uuid));
		set_ble_state(CENTRAL_STATE_FINDING_SERVICE);
		int err = find_service(sensor_conn, uuid);
		if (err) {
			discover_failed_handler(sensor_conn, err);
		}
	}
}

static void discover_failed_handler(struct bt_conn *conn, int err)
{
	LOG_ERR("Discover failed (err %d)", err);
	/* couldn't discover something, disconnect */
	bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
}

/* This callback is triggered when notifications from remote device are received */
static uint8_t notify_func_callback(struct bt_conn *conn,
				    struct bt_gatt_subscribe_params *params,
				    const void *data, uint16_t length)
{
	int32_t reading;
	if (conn != sensor_conn) {
		return BT_GATT_ITER_CONTINUE;
	}

	/* Bug 16486: Zephyr 2.x - Retest NULL notifications that occur when
	* BL654 sensor when CONFIG_HW_STACK_PROTECTION=y, CONFIG_STACK_SENTINEL=y,
	* and CONFIG_STACK_CANARIES=y are set. */
	if (!data) {
		if (params->value_handle ==
		    remote.temperature_subscribe_params.value_handle) {
			LOG_WRN("Unsubscribed from temperature");
		} else if (params->value_handle ==
			   remote.humidity_subscribe_params.value_handle) {
			LOG_WRN("Unsubscribed from humidity");
		} else if (params->value_handle ==
			   remote.pressure_subscribe_params.value_handle) {
			LOG_WRN("Unsubscribed from pressure");
		}
		k_work_schedule(&discover_services_work,
				K_SECONDS(DISCOVER_SERVICES_DELAY_SECONDS));
		params->value_handle = 0;
		return BT_GATT_ITER_STOP;
	}

	/* Check if the notifications received have the temperature handle */
	if (params->value_handle ==
	    remote.temperature_subscribe_params.value_handle) {
		/* Temperature is a 16 bit value */
		int8_t temperature_data[2];
		memcpy(temperature_data, data, length);
		reading = (int16_t)((temperature_data[1] << 8 & 0xFF00) +
				    temperature_data[0]);
		LOG_DBG("ESS Temperature value = %d", reading);
		sensor_aggregator(SENSOR_TYPE_TEMPERATURE, reading);
	}
	/* Check if the notifications received have the humidity handle */
	else if (params->value_handle ==
		 remote.humidity_subscribe_params.value_handle) {
		/* Humidity is a 16 bit value */
		uint8_t humidity_data[2];
		memcpy(humidity_data, data, length);
		reading = ((humidity_data[1] << 8) & 0xFF00) + humidity_data[0];
		LOG_DBG("ESS Humidity value = %d", reading);
		sensor_aggregator(SENSOR_TYPE_HUMIDITY, reading);
	}
	/* Check if the notifications received have the pressure handle */
	else if (params->value_handle ==
		 remote.pressure_subscribe_params.value_handle) {
		/* Pressure is a 32 bit value */
		uint8_t pressure_data[4];
		memcpy(pressure_data, data, length);
		reading = ((pressure_data[3] << 24) & 0xFF000000) +
			  ((pressure_data[2] << 16) & 0xFF0000) +
			  ((pressure_data[1] << 8) & 0xFF00) + pressure_data[0];
		LOG_DBG("ESS Pressure value = %d", reading);
		sensor_aggregator(SENSOR_TYPE_PRESSURE, reading);
	}

	return BT_GATT_ITER_CONTINUE;
}

/* This function is used to discover descriptors in remote device */
static int find_desc(struct bt_conn *conn, struct bt_uuid_16 uuid,
		     uint16_t start_handle)
{
	int err;

	/* Update discover parameters before initiating discovery */
	memcpy(&last_searched_uuid, &uuid, sizeof(last_searched_uuid));
	discover_params.type = BT_GATT_DISCOVER_DESCRIPTOR;
	discover_params.uuid = &last_searched_uuid.uuid;
	discover_params.start_handle = start_handle;
	discover_params.func = desc_discover_func;

	/* Call zephyr library function */
	err = bt_gatt_discover(conn, &discover_params);

	return err;
}

/* This function is used to discover characteristics in remote device */
static int find_char(struct bt_conn *conn, struct bt_uuid_16 n_uuid)
{
	int err;
	if (conn != sensor_conn) {
		return BT_GATT_ITER_CONTINUE;
	}

	/* Update discover parameters before initiating discovery */
	memcpy(&last_searched_uuid, &uuid, sizeof(last_searched_uuid));
	discover_params.type = BT_GATT_DISCOVER_CHARACTERISTIC;
	discover_params.uuid = &last_searched_uuid.uuid;
	discover_params.start_handle = remote.ess_service_handle;
	discover_params.func = char_discover_func;

	/* Call zephyr library function */
	err = bt_gatt_discover(conn, &discover_params);

	return err;
}

/* This function is used to discover services in remote device */
static int find_service(struct bt_conn *conn, struct bt_uuid_16 n_uuid)
{
	int err;

	/* Update discover parameters before initiating discovery */
	memcpy(&last_searched_uuid, &uuid, sizeof(last_searched_uuid));
	discover_params.type = BT_GATT_DISCOVER_PRIMARY;
	discover_params.uuid = &last_searched_uuid.uuid;
	discover_params.start_handle = 0x0001;
	discover_params.end_handle = 0xffff;
	discover_params.func = service_discover_func;

	/* Call zephyr library function */
	err = bt_gatt_discover(sensor_conn, &discover_params);
	return err;
}

/* This callback is triggered when remote descriptors are discovered */
static uint8_t desc_discover_func(struct bt_conn *conn,
				  const struct bt_gatt_attr *attr,
				  struct bt_gatt_discover_params *params)
{
	int err;
	if (conn != sensor_conn) {
		return BT_GATT_ITER_CONTINUE;
	}

	if (remote.app_state == CENTRAL_STATE_FINDING_ESS_TEMPERATURE_CHAR) {
		/* Found temperature CCCD, enable notifications and move on */
		remote.temperature_subscribe_params.notify =
			notify_func_callback;
		remote.temperature_subscribe_params.value = BT_GATT_CCC_NOTIFY;
		remote.temperature_subscribe_params.ccc_handle = attr->handle;
		err = bt_gatt_subscribe(conn,
					&remote.temperature_subscribe_params);
		if (err && err != -EALREADY) {
			LOG_ERR("Subscribe failed (err %d)", err);
		} else {
			LOG_INF("Notifications enabled for temperature characteristic");

			/* Now go on to find humidity characteristic */
			memcpy(&uuid, BT_UUID_HUMIDITY, sizeof(uuid));
			err = find_char(conn, uuid);

			if (err) {
				discover_failed_handler(conn, err);
			} else {
				/* everything looks good, update state to looking for humidity char */
				set_ble_state(
					CENTRAL_STATE_FINDING_ESS_HUMIDITY_CHAR);
			}
		}
	} else if (remote.app_state ==
		   CENTRAL_STATE_FINDING_ESS_HUMIDITY_CHAR) {
		/* Found humidity CCCD, enable notifications and move on */
		remote.humidity_subscribe_params.notify = notify_func_callback;
		remote.humidity_subscribe_params.value = BT_GATT_CCC_NOTIFY;
		remote.humidity_subscribe_params.ccc_handle = attr->handle;
		err = bt_gatt_subscribe(conn,
					&remote.humidity_subscribe_params);
		if (err && err != -EALREADY) {
			LOG_ERR("Subscribe failed (err %d)", err);
		} else {
			LOG_INF("Notifications enabled for humidity characteristic");
			/* Now go on to find pressure characteristic */

			memcpy(&uuid, BT_UUID_PRESSURE, sizeof(uuid));
			err = find_char(conn, uuid);

			if (err) {
				discover_failed_handler(conn, err);
			} else {
				/* everything looks good, update state to looking for pressure char */
				set_ble_state(
					CENTRAL_STATE_FINDING_ESS_PRESSURE_CHAR);
			}
		}
	} else if (remote.app_state ==
		   CENTRAL_STATE_FINDING_ESS_PRESSURE_CHAR) {
		/* Found pressure CCCD, enable notifications and move on */
		remote.pressure_subscribe_params.notify = notify_func_callback;
		remote.pressure_subscribe_params.value = BT_GATT_CCC_NOTIFY;
		remote.pressure_subscribe_params.ccc_handle = attr->handle;
		err = bt_gatt_subscribe(conn,
					&remote.pressure_subscribe_params);
		if (err && err != -EALREADY) {
			LOG_ERR("Subscribe failed (err %d)", err);
		} else {
			LOG_INF("Notifications enabled for pressure characteristic");
			set_ble_state(CENTRAL_STATE_CONNECTED_AND_CONFIGURED);
		}
	}

	return BT_GATT_ITER_STOP;
}

/* This callback is triggered when remote characteristics are discovered */
static uint8_t char_discover_func(struct bt_conn *conn,
				  const struct bt_gatt_attr *attr,
				  struct bt_gatt_discover_params *params)
{
	bool found = false;
	uint16_t value_handle = 0;

	if (conn != sensor_conn) {
		return BT_GATT_ITER_CONTINUE;
	}

	value_handle = bt_gatt_attr_value_handle(attr);
	if (!bt_uuid_cmp(discover_params.uuid, BT_UUID_TEMPERATURE)) {
		LOG_DBG("Found ESS Temperature characteristic");
		remote.temperature_subscribe_params.value_handle = value_handle;
		found = true;
	} else if (!bt_uuid_cmp(discover_params.uuid, BT_UUID_HUMIDITY)) {
		LOG_DBG("Found ESS Humidity characteristic");
		remote.humidity_subscribe_params.value_handle = value_handle;
		found = true;
	} else if (!bt_uuid_cmp(discover_params.uuid, BT_UUID_PRESSURE)) {
		LOG_DBG("Found ESS Pressure characteristic");
		remote.pressure_subscribe_params.value_handle = value_handle;
		found = true;
	}

	if (found) {
		/* Now start searching for CCCD */
		memcpy(&uuid, BT_UUID_GATT_CCC, sizeof(uuid));
		int err = find_desc(conn, uuid,
				    LBT_NEXT_HANDLE_AFTER_CHAR(attr->handle));
		if (err) {
			discover_failed_handler(conn, err);
		}
	}
	return BT_GATT_ITER_STOP;
}

/* This callback is triggered when remote services are discovered */
static uint8_t service_discover_func(struct bt_conn *conn,
				     const struct bt_gatt_attr *attr,
				     struct bt_gatt_discover_params *params)
{
	int err;
	if (conn != sensor_conn) {
		return BT_GATT_ITER_CONTINUE;
	}

	if (!attr) {
		LOG_DBG("Discover complete");
		(void)memset(params, 0, sizeof(*params));
		return BT_GATT_ITER_STOP;
	}

	if (!bt_uuid_cmp(discover_params.uuid, BT_UUID_ESS)) {
		/* Found ESS Service, start searching for temperature char */
		LOG_DBG("Found ESS Service");
		/* Update service handle global variable as it will be used when searching for chars */
		remote.ess_service_handle =
			LBT_NEXT_HANDLE_AFTER_SERVICE(attr->handle);
		/* Start looking for temperature characteristic */
		memcpy(&uuid, BT_UUID_TEMPERATURE, sizeof(uuid));
		err = find_char(conn, uuid);
		if (err) {
			discover_failed_handler(conn, err);
		} else {
			/* Looking for temperature char, update state */
			set_ble_state(
				CENTRAL_STATE_FINDING_ESS_TEMPERATURE_CHAR);
		}
	}

	return BT_GATT_ITER_STOP;
}

/* This callback is triggered when a BLE connection occurs */
static void connected(struct bt_conn *conn, uint8_t err)
{
	char addr[BT_ADDR_LE_STR_LEN];
	if (conn != sensor_conn) {
		return;
	}

	bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));

	if (err) {
		goto fail;
	}

	LOG_INF("Connected sensor: %s", log_strdup(addr));
	attr_set_string(ATTR_ID_sensor_bluetooth_address, addr, strlen(addr));

	/* Wait some time before discovering services.
	 * After a connection the BL654 Sensor disables
	 * characteristic notifications.
	 * We dont want that to interfere with use enabling
	 * notifications when we discover characteristics
	 */
	k_work_schedule(&discover_services_work,
			K_SECONDS(DISCOVER_SERVICES_DELAY_SECONDS));

	return;

fail:
	LOG_ERR("Failed to connect to sensor %s (%u %s)", log_strdup(addr), err,
		lbt_get_hci_err_string(err));
	bt_conn_unref(conn);
	sensor_conn = NULL;
	/* Set state to searching */
	set_ble_state(CENTRAL_STATE_FINDING_DEVICE);
}

/* This callback is triggered when a BLE disconnection occurs */
static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	char addr[BT_ADDR_LE_STR_LEN];
	if (conn != sensor_conn) {
		return;
	}

	bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));

	LOG_INF("Disconnected sensor: %s (reason %u %s)", log_strdup(addr),
		reason, lbt_get_hci_err_string(reason));

	bt_conn_unref(conn);
	sensor_conn = NULL;

	/* Set state to searching */
	set_ble_state(CENTRAL_STATE_FINDING_DEVICE);
}

static void set_ble_state(enum central_state state)
{
	remote.app_state = state;
	attr_set_uint32(ATTR_ID_central_state, state);

	switch (state) {
	case CENTRAL_STATE_CONNECTED_AND_CONFIGURED:
#ifdef HAS_SECOND_BLUETOOTH_LED
		lcz_led_turn_on(BLUETOOTH_LED);
#endif
		lcz_bt_scan_resume(scan_id);
		break;

	case CENTRAL_STATE_FINDING_DEVICE:
#ifdef HAS_SECOND_BLUETOOTH_LED
		lcz_led_blink(BLUETOOTH_LED, &LED_SENSOR_SEARCH_PATTERN);
#endif
		attr_set_string(ATTR_ID_sensor_bluetooth_address, "", 0);
		lcz_bt_scan_restart(scan_id);
		break;

	default:
		/* Nothing needs to be done for these states. */
		break;
	}
}

static void sensor_aggregator(uint8_t sensor, int32_t reading)
{
	static int64_t bmeEventTime = 0;
	/* On init, send first data immediately. */
	static int64_t delta =
		(CONFIG_ESS_SENSOR_SEND_TO_AWS_RATE_SECONDS * MSEC_PER_SEC);

	if (sensor == SENSOR_TYPE_TEMPERATURE) {
		/* Divide by 100 to get xx.xxC format */
		temperature = reading / 100.0;
		updated_temperature = true;
	} else if (sensor == SENSOR_TYPE_HUMIDITY) {
		/* Divide by 100 to get xx.xx% format */
		humidity = reading / 100.0;
		updated_humidity = true;
	} else if (sensor == SENSOR_TYPE_PRESSURE) {
		/* Divide by 10 to get x.xPa format */
		pressure = reading / 10.0;
		updated_pressure = true;
	}

	delta += k_uptime_delta(&bmeEventTime);
	if (delta <
	    (CONFIG_ESS_SENSOR_SEND_TO_AWS_RATE_SECONDS * MSEC_PER_SEC)) {
		return;
	}

	if (updated_temperature && updated_humidity && updated_pressure) {
		ESSSensorMsg_t *pMsg =
			BP_TRY_TO_TAKE(sizeof(ESSSensorMsg_t));
		if (pMsg == NULL) {
			LOG_ERR("Bad memory allocation. Resetting...");
			wdt_force();			
			return;
		}
		pMsg->header.msgCode = FMC_ESS_SENSOR_EVENT;
		pMsg->header.rxId = FWK_ID_CLOUD;
		pMsg->temperatureC = temperature;
		pMsg->humidityPercent = humidity;
		pMsg->pressurePa = pressure;

#ifdef CONFIG_SD_CARD_LOG
		sdCardLogESSData(pMsg);
#endif

		FRAMEWORK_MSG_SEND(pMsg);
		updated_temperature = false;
		updated_humidity = false;
		updated_pressure = false;
		delta = 0;
	}
}
