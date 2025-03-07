/**
 * @file lcz_modem_shell.c
 * @brief
 *
 * Copyright (c) 2020-2021 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/******************************************************************************/
/* Includes                                                                   */
/******************************************************************************/
#include <zephyr.h>
#include <shell/shell.h>
#include <init.h>
#include <stdio.h>
#include <stdlib.h>

#include <drivers/modem/hl7800.h>
#include "attr.h"

/******************************************************************************/
/* Global Constants, Macros and Type Definitions                              */
/******************************************************************************/
#define APN_MSG "APN: [%s]"

#define ARG_STR(x) x ? x : "null"

#ifndef CONFIG_MODEM_LOG_LEVEL
#define CONFIG_MODEM_LOG_LEVEL 0
#endif

#define AT_CMD_LOG_DBG_SECONDS 1

/******************************************************************************/
/* Global Data Definitions                                                    */
/******************************************************************************/
extern struct mdm_hl7800_apn *lte_apn_config;

/******************************************************************************/
/* Local Function Prototypes                                                  */
/******************************************************************************/
static void log_restore_handler(struct k_work *work);

/******************************************************************************/
/* Local Data Definitions                                                     */
/******************************************************************************/
static K_WORK_DELAYABLE_DEFINE(log_work, log_restore_handler);

/******************************************************************************/
/* Local Function Definitions                                                 */
/******************************************************************************/
/**
 * @note The log level cannot be set higher than its compiled level.
 * Viewing the response to many AT commands requires that the log level
 * is DEBUG.
 */
static int shell_send_at_cmd(const struct shell *shell, size_t argc,
			     char **argv)
{
	int rc = 0;
	long log_restore_delay;

	if ((argc == 3) && (argv[1] != NULL) && (argv[2] != NULL)) {
		mdm_hl7800_log_filter_set(LOG_LEVEL_DBG);
		rc = mdm_hl7800_send_at_cmd(argv[2]);
		if (rc < 0) {
			shell_error(shell, "Command not accepted");
		}
		log_restore_delay = strtol(argv[1], NULL, 0);
		log_restore_delay =
			MAX(AT_CMD_LOG_DBG_SECONDS, log_restore_delay);
		k_work_schedule(&log_work, K_SECONDS(log_restore_delay));
	} else {
		shell_error(shell,
			    "Invalid parameter"
			    "argc: %d argv[0]: %s argv[1]: %s argv[2]: %s",
			    argc, ARG_STR(argv[0]), ARG_STR(argv[1]),
			    ARG_STR(argv[2]));

		rc = -EINVAL;
	}

	return rc;
}

static void log_restore_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	mdm_hl7800_log_filter_set(
		attr_get_uint32(ATTR_ID_modem_desired_log_level, LOG_LEVEL_DBG));
}

static int shell_hl_apn_cmd(const struct shell *shell, size_t argc, char **argv)
{
	int rc = 0;

	size_t val_len;

	if (argc == 2) {
		/* set the value */
		val_len = strlen(argv[1]);
		if (val_len > MDM_HL7800_APN_MAX_SIZE) {
			rc = -EINVAL;
			shell_error(shell, "APN too long [%d]", val_len);
			goto done;
		}

		rc = mdm_hl7800_update_apn(argv[1]);
		if (rc >= 0) {
			shell_print(shell, APN_MSG, argv[1]);
		} else {
			shell_error(shell, "Could not set APN [%d]", rc);
		}
	} else if (argc == 1) {
		/* read the value */
		shell_print(shell, APN_MSG, lte_apn_config->value);
	} else {
		shell_error(shell, "Invalid param");
		rc = -EINVAL;
	}
done:
	return rc;
}

#ifdef CONFIG_MODEM_HL7800_FW_UPDATE
static int shell_hl_fup_cmd(const struct shell *shell, size_t argc, char **argv)
{
	int rc = 0;

	if ((argc == 2) && (argv[1] != NULL)) {
		rc = mdm_hl7800_update_fw(argv[1]);
		if (rc < 0) {
			shell_error(shell, "Command error");
		}
	} else {
		shell_error(shell, "Invalid parameter");
		rc = -EINVAL;
	}

	return rc;
}
#endif /* CONFIG_MODEM_HL7800_FW_UPDATE */

static int shell_hl_iccid_cmd(const struct shell *shell, size_t argc,
			      char **argv)
{
	int rc = 0;

	shell_print(shell, "%s", mdm_hl7800_get_iccid());

	return rc;
}

static int shell_hl_imei_cmd(const struct shell *shell, size_t argc,
			     char **argv)
{
	int rc = 0;

	shell_print(shell, "%s", mdm_hl7800_get_imei());

	return rc;
}

static int shell_hl_sn_cmd(const struct shell *shell, size_t argc, char **argv)
{
	int rc = 0;

	shell_print(shell, "%s", mdm_hl7800_get_sn());

	return rc;
}

static int shell_hl_ver_cmd(const struct shell *shell, size_t argc, char **argv)
{
	int rc = 0;

	shell_print(shell, "%s", mdm_hl7800_get_fw_version());

	return rc;
}

static int shell_hl_site_survey_cmd(const struct shell *shell, size_t argc,
				    char **argv)
{
	int rc = 0;

	shell_print(shell, "survey status: %d",
		    mdm_hl7800_perform_site_survey());

	/* Results are printed to shell by lte.site_survey_handler() */

	return rc;
}

/******************************************************************************/
/* Global Function Definitions                                                */
/******************************************************************************/
SHELL_STATIC_SUBCMD_SET_CREATE(
	hl_cmds, SHELL_CMD(apn, NULL, "HL7800 APN", shell_hl_apn_cmd),
	SHELL_CMD(
		cmd, NULL,
		"Send AT command (only for advanced debug)"
		"hl cmd <return to normal log level delay seconds> <at command>",
		shell_send_at_cmd),
#ifdef CONFIG_MODEM_HL7800_FW_UPDATE
	SHELL_CMD(fup, NULL, "Update HL7800 firmware", shell_hl_fup_cmd),
#endif
	SHELL_CMD(iccid, NULL, "HL7800 SIM card ICCID", shell_hl_iccid_cmd),
	SHELL_CMD(imei, NULL, "HL7800 IMEI", shell_hl_imei_cmd),
	SHELL_CMD(sn, NULL, "HL7800 serial number", shell_hl_sn_cmd),
	SHELL_CMD(ver, NULL, "HL7800 firmware version", shell_hl_ver_cmd),
	SHELL_CMD(survey, NULL, "HL7800 site survey", shell_hl_site_survey_cmd),
	SHELL_SUBCMD_SET_END /* Array terminated. */
);

SHELL_CMD_REGISTER(hl, &hl_cmds, "HL7800 commands", NULL);
