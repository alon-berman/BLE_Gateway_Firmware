/**
 * @file gateway_common.c
 * @brief
 *
 * Copyright (c) 2021 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <logging/log.h>
LOG_MODULE_REGISTER(gateway_common, CONFIG_GATEWAY_LOG_LEVEL);

/******************************************************************************/
/* Includes                                                                   */
/******************************************************************************/
#include <zephyr.h>

#include "led_configuration.h"
#include "lte.h"
#include "attr.h"
#include "ble.h"
#include "dis.h"
#include "FrameworkIncludes.h"
#include "laird_utility_macros.h"
#include "lcz_bluetooth.h"
#include "single_peripheral.h"
#include "string_util.h"
#include "app_version.h"
#include "lcz_bt_scan.h"
#include "button.h"
#include "lcz_software_reset.h"
#include "sdcard_log.h"
#include "file_system_utilities.h"
#include "gateway_fsm.h"
#include "lcz_qrtc.h"

#ifdef CONFIG_LCZ_POWER
#include "laird_power.h"
#endif

#ifdef CONFIG_BOARD_MG100
#include "lairdconnect_battery.h"
#endif

#ifdef CONFIG_LCZ_MOTION
#include "lcz_motion.h"
#endif

#ifdef CONFIG_LCZ_NFC
#include "laird_connectivity_nfc.h"
#endif

#ifdef CONFIG_ESS_SENSOR
#include "ess_sensor.h"
#endif

#ifdef CONFIG_BLUEGRASS
#include "aws.h"
#include "bluegrass.h"
#endif

#ifdef CONFIG_LWM2M
#include "lcz_lwm2m_client.h"
#include "memfault_task.h"
#endif

#ifdef CONFIG_MCUMGR
#include "mcumgr_wrapper.h"
#endif

#if defined(CONFIG_BLUEGRASS) && defined(CONFIG_COAP_FOTA)
#include "coap_fota_task.h"
#endif

#if defined(CONFIG_BLUEGRASS) && defined(CONFIG_HTTP_FOTA)
#include "http_fota_task.h"
#endif

#include "lcz_memfault.h"

#ifdef CONFIG_CONTACT_TRACING
#include "ct_app.h"
#include "ct_ble.h"
#endif

#ifdef CONFIG_DFU_TARGET_MCUBOOT
#include <dfu/mcuboot.h>
#endif

#ifdef CONFIG_DISPLAY
#include "lcd.h"
#endif

#include "gateway_common.h"

/******************************************************************************/
/* Local Constant, Macro and Type Definitions                                 */
/******************************************************************************/
#define RESET_COUNT_FNAME CONFIG_FSU_MOUNT_POINT "/reset_count"

/******************************************************************************/
/* Local Data Definitions                                                     */
/******************************************************************************/
#if defined(CONFIG_LCZ_LWM2M_SENSOR)
static struct bt_le_scan_param gw_scan_parameters = BT_LE_SCAN_PARAM_INIT(
	BT_LE_SCAN_TYPE_ACTIVE,
	BT_LE_SCAN_OPT_CODED | BT_LE_SCAN_OPT_FILTER_DUPLICATE,
	CONFIG_LCZ_BT_SCAN_DEFAULT_INTERVAL, CONFIG_LCZ_BT_SCAN_DEFAULT_WINDOW);
#elif defined(CONFIG_SCAN_FOR_BT510_CODED)
static struct bt_le_scan_param gw_scan_parameters = BT_LE_SCAN_PARAM_INIT(
	BT_LE_SCAN_TYPE_ACTIVE,
	BT_LE_SCAN_OPT_CODED | BT_LE_SCAN_OPT_FILTER_DUPLICATE,
	CONFIG_LCZ_BT_SCAN_DEFAULT_INTERVAL, CONFIG_LCZ_BT_SCAN_DEFAULT_WINDOW);
#elif defined(CONFIG_SCAN_FOR_BT510)
static struct bt_le_scan_param gw_scan_parameters = BT_LE_SCAN_PARAM_INIT(
	BT_LE_SCAN_TYPE_ACTIVE, BT_LE_SCAN_OPT_FILTER_DUPLICATE,
	CONFIG_LCZ_BT_SCAN_DEFAULT_INTERVAL, CONFIG_LCZ_BT_SCAN_DEFAULT_WINDOW);
#endif

/******************************************************************************/
/* Local Function Prototypes                                                  */
/******************************************************************************/
static void configure_leds(void);
static void configure_button(void);
static void reset_reason_cleared_by_memfault_handler(void);
static void reset_reason_not_cleared_by_memfault_handler(void);
static void reset_reason_handler(void);
static void reset_count_handler(void);
static void app_type_handler(void);
static void reboot_handler(void);
static void configure_sd_card(void);
static void advertise_on_startup(void);

#ifndef CONFIG_CONTACT_TRACING
static int adv_on_button_isr(void);
#endif

#ifdef CONFIG_BLUEGRASS
static void aws_set_default_client_id(void);
#endif

#ifdef CONFIG_MODEM_HL7800
static void fs_to_attr_string_handler(attr_index_t idx, const char *file_name);
static void nv_deprecation_handler(void);
#endif

/******************************************************************************/
/* Global Function Definitions                                                */
/******************************************************************************/
int configure_app(void)
{
	MFLT_METRICS_TIMER_START(lte_ttf);

	configure_leds();

	configure_button();

	configure_sd_card();

	reboot_handler();

#ifndef CONFIG_LWM2M
	LCZ_MEMFAULT_HTTP_INIT();
#endif

#ifdef CONFIG_MODEM_HL7800
	nv_deprecation_handler();
#endif

#if defined(CONFIG_LCZ_LWM2M_SENSOR) ||                                        \
	defined(CONFIG_SCAN_FOR_BT510_CODED) || defined(CONFIG_SCAN_FOR_BT510)
	if (!lcz_bt_scan_set_parameters(&gw_scan_parameters)) {
		LOG_ERR("Unable to set scan parameters");
	}
#endif

#ifdef CONFIG_ESS_SENSOR
	ess_sensor_initialize();
#endif

#ifdef CONFIG_BLUEGRASS
	aws_set_default_client_id();
	awsInit();
#endif

#ifdef CONFIG_BLUEGRASS
	bluegrass_initialize();
#endif

	dis_initialize(APP_VERSION_STRING);

#ifdef CONFIG_FOTA_SERVICE
	fota_init();
#endif

#ifdef CONFIG_BOARD_MG100
	/* Initialize the battery management sub-system.
	 * NOTE: This must be executed after parameter system initialization.
	 */
	BatteryInit();
#endif

#ifdef CONFIG_LCZ_MOTION
	lcz_motion_init();
#endif

#ifdef CONFIG_LCZ_POWER
	/* Start periodic ADC conversions (after battery init for mg100) */
	power_init();
	power_mode_set(true);
#endif

#ifdef CONFIG_LCZ_NFC
	laird_connectivity_nfc_init();
#endif

#ifdef CONFIG_LCZ_MCUMGR_WRAPPER
	mcumgr_wrapper_register_subsystems();
#endif

#if defined(CONFIG_BLUEGRASS) && defined(CONFIG_COAP_FOTA)
	coap_fota_task_initialize();
#endif
#if defined(CONFIG_BLUEGRASS) && defined(CONFIG_HTTP_FOTA)
	http_fota_task_initialize();
#endif

#ifdef CONFIG_CONTACT_TRACING
	ct_app_init();
#endif

#ifdef CONFIG_DISPLAY
	lcd_display_init();
	lcd_display_update_details();
#endif

	advertise_on_startup();

#ifdef CONFIG_DFU_TARGET_MCUBOOT
	/* if we've gotten this far, assume the image is ok */
	if (!boot_is_img_confirmed()) {
		boot_write_img_confirmed();
	}
#endif

	return 0;
}

/******************************************************************************/
/* Override weak implementations                                              */
/******************************************************************************/
/**
 * @brief Wait until network init has completed before reading radio
 * information because it won't be valid until then.
 */
void gateway_fsm_network_init_complete_callback(void)
{
#ifdef CONFIG_MODEM_HL7800
	ble_update_name(attr_get_quasi_static(ATTR_ID_gateway_id));
#endif

#ifdef CONFIG_CONTACT_TRACING
	ct_ble_topic_builder();
#endif
}

void gateway_fsm_network_connected_callback(void)
{
#ifdef CONFIG_MODEM_HL7800
	if (*(uint8_t *)attr_get_quasi_static(ATTR_ID_lte_rat) == LTE_RAT_CAT_M1)
#endif
	{
#ifdef CONFIG_LWM2M
		LCZ_LWM2M_MEMFAULT_POST_DATA();
#else
		LCZ_MEMFAULT_POST_DATA();
#endif
	}

#ifdef CONFIG_LWM2M
	int rc;

	rc = lwm2m_client_init();
	if (rc != 0) {
		LOG_ERR("LwM2M init [%d]", rc);
	}
#endif

	FRAMEWORK_MSG_CREATE_AND_BROADCAST(FWK_ID_RESERVED,
					   FMC_NETWORK_CONNECTED);
}

void gateway_fsm_network_disconnected_callback(void)
{
	FRAMEWORK_MSG_CREATE_AND_BROADCAST(FWK_ID_RESERVED,
					   FMC_NETWORK_DISCONNECTED);
}

void gateway_fsm_cloud_connected_callback(void)
{
	FRAMEWORK_MSG_CREATE_AND_BROADCAST(FWK_ID_RESERVED,
					   FMC_CLOUD_CONNECTED);
}

void gateway_fsm_cloud_disconnected_callback(void)
{
	FRAMEWORK_MSG_CREATE_AND_BROADCAST(FWK_ID_RESERVED,
					   FMC_CLOUD_DISCONNECTED);
}

int attr_prepare_upTime(void)
{
	return attr_set_signed64(ATTR_ID_up_time, k_uptime_get());
}

int attr_prepare_qrtc(void)
{
	return attr_set_uint32(ATTR_ID_qrtc, lcz_qrtc_get_epoch());
}

#ifdef CONFIG_MODEM_HL7800
int attr_prepare_modemBoot(void)
{
#if defined(CONFIG_MODEM_HL7800_BOOT_DELAY)
	return attr_set_uint32(ATTR_ID_modemBoot, MODEM_BOOT_DELAYED);
#elif defined(CONFIG_MODEM_HL7800_BOOT_IN_AIRPLANE_MODE)
	return attr_set_uint32(ATTR_ID_modemBoot, MODEM_BOOT_AIRPLANE);
#else
	return attr_set_uint32(ATTR_ID_modem_boot, MODEM_BOOT_NORMAL);
#endif
}
#endif

void Framework_AssertionHandler(char *file, int line)
{
	static atomic_t busy = ATOMIC_INIT(0);
	/* prevent recursion (buffer alloc fail, ...) */
	if (!busy) {
		atomic_set(&busy, 1);
		LOG_ERR("\r\n!---> Framework Assertion <---! %s:%d\r\n", file,
			line);
		LOG_ERR("Thread name: %s",
			log_strdup(k_thread_name_get(k_current_get())));
	}

	lcz_software_reset_after_assert(CONFIG_FWK_RESET_DELAY_MS);
}

#ifdef CONFIG_LCZ_POWER
/* Override weak implementation in laird_power.c */
void power_measurement_callback(uint8_t integer, uint8_t decimal)
{
	uint16_t voltage_mv = (integer * 1000) + decimal;

	if (voltage_mv > CONFIG_MIN_POWER_MEASUREMENT_MV) {
#ifdef CONFIG_BOARD_MG100
		BatteryCalculateRemainingCapacity(voltage_mv);
#else
		attr_set_float(ATTR_ID_power_supply_voltage,
			       ((float)voltage_mv) / 1000.0);
#endif
	}
}
#endif

#ifdef CONFIG_LCZ_MOTION
void lcz_motion_set_alarm_state(uint8_t state)
{
	attr_set_uint32(ATTR_ID_motion_alarm, state);
}
#endif

#ifdef CONFIG_MCUMGR_CMD_SENTRIUS_MGMT
int sentrius_mgmt_led_test(uint32_t duration)
{
	led_index_t i;

	/* LED status may not be valid after running this command. */
	for (i = 0; i < CONFIG_LCZ_NUMBER_OF_LEDS; i++) {
		lcz_led_turn_on(i);
		k_sleep(K_MSEC(duration));
		lcz_led_turn_off(i);
	}

	return 0;
}

int sentrius_mgmt_factory_reset(void)
{
	FRAMEWORK_MSG_CREATE_AND_SEND(FWK_ID_CONTROL_TASK, FWK_ID_CONTROL_TASK,
				      FMC_FACTORY_RESET);

	return 0;
}
#endif

/******************************************************************************/
/* Local Function Definitions                                                 */
/******************************************************************************/
/* This is an example of using a file.
 * The count could be handled entirely by the attribute module.
 */
static void reset_count_handler(void)
{
	uint32_t count = 0;

	if (fsu_lfs_mount() == 0) {
		fsu_read_abs(RESET_COUNT_FNAME, &count, sizeof(count));
		count += 1;
		fsu_write_abs(RESET_COUNT_FNAME, &count, sizeof(count));
	}
	attr_set_uint32(ATTR_ID_reset_count, count);
}

static void app_type_handler(void)
{
	extern const char *get_app_type(void);
	const char *app_type = get_app_type();

	attr_set_string(ATTR_ID_app_type, app_type, strlen(app_type));
}

static void reboot_handler(void)
{
	reset_reason_handler();
	reset_count_handler();
	app_type_handler();
	attr_set_string(ATTR_ID_firmware_version, APP_VERSION_STRING,
			strlen(APP_VERSION_STRING));
	attr_set_string(ATTR_ID_board, CONFIG_BOARD, strlen(CONFIG_BOARD));
}

static void configure_leds(void)
{
#if defined(CONFIG_BOARD_MG100)
	struct lcz_led_configuration c[] = {
		{ BLUE_LED, LED2_DEV, LED2, LED_ACTIVE_HIGH },
		{ GREEN_LED, LED3_DEV, LED3, LED_ACTIVE_HIGH },
		{ RED_LED, LED1_DEV, LED1, LED_ACTIVE_HIGH }
	};
#elif defined(CONFIG_BOARD_PINNACLE_100_DVK)
	struct lcz_led_configuration c[] = {
		{ BLUE_LED, LED1_DEV, LED1, LED_ACTIVE_HIGH },
		{ GREEN_LED, LED2_DEV, LED2, LED_ACTIVE_HIGH },
		{ RED_LED, LED3_DEV, LED3, LED_ACTIVE_HIGH },
		{ GREEN_LED2, LED4_DEV, LED4, LED_ACTIVE_HIGH }
	};
#elif defined(CONFIG_BOARD_BL5340_DVK_CPUAPP) ||                               \
	defined(CONFIG_BOARD_BL5340PA_DVK_CPUAPP)
	struct lcz_led_configuration c[] = {
		{ BLUE_LED1, LED1_DEV, LED1, LED_ACTIVE_LOW },
		{ BLUE_LED2, LED2_DEV, LED2, LED_ACTIVE_LOW },
		{ BLUE_LED3, LED3_DEV, LED3, LED_ACTIVE_LOW },
		{ BLUE_LED4, LED4_DEV, LED4, LED_ACTIVE_LOW }
	};
#else
#error "Unsupported board selected"
#endif
	lcz_led_init(c, ARRAY_SIZE(c));
}

static void configure_button(void)
{
#ifdef CONFIG_CONTACT_TRACING
	static const button_config_t BUTTON_CONFIG[] = {
		{ 50, 0, ct_adv_on_button_isr }
	};
#else
	static const button_config_t BUTTON_CONFIG[] = {
		{ 50, 0, adv_on_button_isr }
	};
#endif

	button_initialize(BUTTON_CONFIG, ARRAY_SIZE(BUTTON_CONFIG), NULL);
}

static void reset_reason_cleared_by_memfault_handler(void)
{
	const char *s = "use memfault";

	attr_set_string(ATTR_ID_reset_reason, s, strlen(s));
}

static void reset_reason_not_cleared_by_memfault_handler(void)
{
	uint32_t reset_reason = lbt_get_and_clear_nrf52_reset_reason_register();
	const char *reset_str =
		lbt_get_nrf52_reset_reason_string_from_register(reset_reason);

	attr_set_string(ATTR_ID_reset_reason, reset_str, strlen(reset_str));

#ifndef CONFIG_LCZ_MEMFAULT
	LOG_WRN("reset reason: %s (%08X)", reset_str, reset_reason);
#endif
}

static void reset_reason_handler(void)
{
	if (IS_ENABLED(CONFIG_MEMFAULT_CLEAR_RESET_REG)) {
		reset_reason_cleared_by_memfault_handler();
	} else {
		reset_reason_not_cleared_by_memfault_handler();
	}
}

#ifndef CONFIG_CONTACT_TRACING
static int adv_on_button_isr(void)
{
	single_peripheral_start_advertising();
	return 0;
}
#endif

/**
 * @brief Advertise on startup after setting name and after CT init.
 * This allows image confirmation from the mobile application during FOTA.
 * Button handling normally happens in ISR context, but in this case it does not.
 */
static void advertise_on_startup(void)
{
#ifdef CONFIG_CONTACT_TRACING
	ct_adv_on_button_isr();
#else
	adv_on_button_isr();
#endif
}

static void configure_sd_card(void)
{
#ifdef CONFIG_SD_CARD_LOG
	int rc;

	rc = sdCardLogInit();
#ifdef CONFIG_CONTACT_TRACING
	if (rc == 0) {
		sdCardLogCleanup();
	}
#endif
#endif
}

#ifdef CONFIG_BLUEGRASS
static void aws_set_default_client_id(void)
{
	const char *s;

	s = attr_get_quasi_static(ATTR_ID_client_id);

	/* Doesn't handle the board changing. */
	if (strlen(s) == 0) {
#if defined(CONFIG_BOARD_BL5340_DVK_CPUAPP)
		s = "bl5340";
#elif defined(CONFIG_BOARD_BL5340PA_DVK_CPUAPP)
		s = "bl5340pa";
#elif defined(CONFIG_BOARD_MG100)
		s = "mg100";
#else
		s = "pinnacle100_oob";
#endif
		attr_set_string(ATTR_ID_client_id, s, strlen(s));
	}
}
#endif

#ifdef CONFIG_MODEM_HL7800
static void fs_to_attr_string_handler(attr_index_t idx, const char *file_name)
{
	int r = -EPERM;
	char buffer[ATTR_MAX_STR_SIZE];

	r = fsu_read(CONFIG_FSU_MOUNT_POINT, file_name, buffer, sizeof(buffer));
	if (r > 0) {
		r = attr_set_string(idx, buffer, strlen(buffer));
		if (r == 0) {
			fsu_delete(CONFIG_FSU_MOUNT_POINT, file_name);
		}
	}
	LOG_DBG("NV/FS Import of %s: %d", attr_get_name(idx), r);
}

/**
 * @brief Read values saved to filesystem in previous version of firmware and
 * import then into the parameter system.
 */
static void nv_deprecation_handler(void)
{
	uint32_t commissioned = 0;
	int r = -EPERM;

	if (attr_get_uint32(ATTR_ID_nv_imported, 0) != 0) {
		return;
	}

	r = fsu_read(CONFIG_FSU_MOUNT_POINT, CONFIG_APP_COMMISSIONED_FILE_NAME,
		     &commissioned, sizeof(commissioned));
	if (r == 1) {
		r = attr_set_uint32(ATTR_ID_commissioned, commissioned);
		fsu_delete(CONFIG_FSU_MOUNT_POINT,
			   CONFIG_APP_COMMISSIONED_FILE_NAME);
	}
	LOG_DBG("Commissioned flag import %d", r);

	fs_to_attr_string_handler(ATTR_ID_client_id,
				  CONFIG_APP_CLIENT_ID_FILE_NAME);
	fs_to_attr_string_handler(ATTR_ID_endpoint,
				  CONFIG_APP_ENDPOINT_FILE_NAME);
	fs_to_attr_string_handler(ATTR_ID_topic_prefix,
				  CONFIG_APP_TOPIC_PREFIX_FILE_NAME);

	/* Import only needs to occur once. */
	attr_set_uint32(ATTR_ID_nv_imported, 1);

	/* Remove file used by previous version to limit writes on reboot. */
	fsu_delete_abs(CONFIG_FSU_MOUNT_POINT "/nv_startup.bin");
}
#endif
