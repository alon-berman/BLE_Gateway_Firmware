/**
 * @file lte.h
 * @brief Abstraction layer between hl7800/network and application.
 *
 * Copyright (c) 2020-2021 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef __LTE_H__
#define __LTE_H__

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/******************************************************************************/
/* Global Function Prototypes                                                 */
/******************************************************************************/
/**
 * @brief Init LTE modem and update modem information
 *
 * @retval 0 on success, lte_init_status enum on failure.
 */
int lte_init(void);

/**
 * @brief Init network
 *
 * @retval 0 on success, lte_init_status enum on failure.
 */
int lte_network_init(void);

/**
 * @brief Accessor
 */
bool lte_ready(void);

/**
 * @brief Check if the LTE network interface is up and ready for
 * DNS and other IP traffic.
 *
 * @return true ready for use
 * @return false not ready for use
 */
bool lte_dns_ready(void);

/**
 * @brief Force set flag indicating LTE network DNS is ready
 *
 */
void set_lte_dns_ready(void);

/**
 * @brief Get the IP address of the LTE network interface
 *
 * @param get_ipv6 true to get the IPv6 address if available
 * @param ip_addr point to buffer to hold the IP address string
 * @param ip_addr_len length of the address string buffer
 * @return int 0 on success
 */
int lte_get_ip_address(bool get_ipv6, char *ip_addr, int ip_addr_len);

/**
 * @brief Hard-reset and reconfigure the HL7800 in place (self-recovery
 * ladder, step 1).  Blocks the caller for the modem boot and configuration
 * sequence (tens of seconds); call from the control task only.
 *
 * @retval 0 on success, negative on error
 */
int lte_recover_modem(void);

/**
 * @brief Number of network registration-loss events since boot (diagnostics,
 * published in the gateway heartbeat as reg_losses).
 */
uint32_t lte_get_registration_losses(void);

/**
 * @brief Number of modem recoveries performed since boot (diagnostics,
 * published in the gateway heartbeat as modem_resets).
 */
uint32_t lte_get_modem_recoveries(void);

#ifdef __cplusplus
}
#endif

#endif /* __LTE_H__ */
