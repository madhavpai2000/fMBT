/*
 * fMBT, free Model Based Testing tool
 * Copyright (c) 2013, Intel Corporation.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms and conditions of the GNU Lesser General Public License,
 * version 2.1, as published by the Free Software Foundation.
 *
 * This program is distributed in the hope it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Lesser General Public License along with
 * this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
 *
 */

/* This program helps launching fMBT Python applications on Windows. */

#include <glib.h>
#include <stdio.h>
#include <string.h>

int main(int argc,char** argv)
{
  gint exit_status;
  int i;

  char** margv;
  g_type_init ();

  margv=(char**)g_new0(char**,argc+2);
  margv[0]="C:\\Python27\\python.exe";

  margv[1]=g_find_program_in_path(argv[0]);

  if (g_str_has_suffix(margv[1],".exe")) {
    margv[1]=g_strndup(margv[1],strlen(margv[1])-4);
  }

  for(i=1;i<argc;i++) {
    margv[i+1]=argv[i];
  }

  g_spawn_sync(NULL,margv,NULL,
	       G_SPAWN_CHILD_INHERITS_STDIN,
	       NULL,NULL,
	       NULL,NULL,
	       &exit_status,NULL);
  return exit_status;
}
