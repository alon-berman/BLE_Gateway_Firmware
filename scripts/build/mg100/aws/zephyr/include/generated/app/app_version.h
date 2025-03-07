/**
 * @file app_version.h
 * @brief
 *
 * Copyright (c) 2020-2021 Laird Connectivity
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef __APP_VERSION_H__
#define __APP_VERSION_H__

#ifdef __cplusplus
extern "C" {
#endif

/******************************************************************************/
/* Application Firmware Version                                               */
/******************************************************************************/
#define APP_VERSION_MAJOR 6
#define APP_VERSION_MINOR 4
#define APP_VERSION_PATCH 1
#define APP_VERSION_BUILD 1666015689
#define APP_VERSION_STRING                                                     \
	STRINGIFY(APP_VERSION_MAJOR)                                           \
	"." STRINGIFY(APP_VERSION_MINOR) "." STRINGIFY(APP_VERSION_PATCH)

#define APP_VERSION_STRING_PLUS_BUILD                                          \
	STRINGIFY(APP_VERSION_MAJOR)                                           \
	"." STRINGIFY(APP_VERSION_MINOR) "." STRINGIFY(                        \
		APP_VERSION_PATCH) "+" STRINGIFY(APP_VERSION_BUILD)

#ifdef __cplusplus
}
#endif

#endif /* __APP_VERSION_H__ */
