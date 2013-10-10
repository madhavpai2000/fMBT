/*
 * fMBT, free Model Based Testing tool
 * Copyright (c) 2011, Intel Corporation.
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

#include "params.hh"
#define _RANDOM_INTERNAL_
#include "random.hh"
#include <stdio.h>

FACTORY_IMPLEMENTATION(Random)

class r_store {
public:
  r_store(): r(NULL) {

  }
  r_store(Random* _r):r(_r) {
    r->ref();
  }
  ~r_store() {
    if (r)
      r->unref();
  }
  Random* r;
};

Random* new_random(const std::string& s) {
  static std::map<const std::string,r_store> static_support;
  std::string name,option;
  param_cut(s,name,option);

  Random* ret=static_support[name].r;

  if (ret) {
    ret->ref();
    return ret;
  }

  ret=RandomFactory::create(name, option);

  if (ret) {
    if (ret->single) {
      static_support[name]=r_store(ret);
    }
    ret->ref();
    return ret;
  }

  //Let's try old thing.
  split(s, name, option);

  ret=static_support[name].r;

  if (ret) {
    ret->ref();
    fprintf(stderr,"DEPRECATED RANDOM SYNTAX. %s\nNew syntax is %s(%s)\n",
	    s.c_str(),name.c_str(),option.c_str());

    return ret;
  }


  ret=RandomFactory::create(name, option);

  if (ret) {
    fprintf(stderr,"DEPRECATED RANDOM SYNTAX. %s\nNew syntax is %s(%s)\n",
	    s.c_str(),name.c_str(),option.c_str());

    if (ret->single) {
      static_support[name]=r_store(ret);
    }
    ret->ref();
  }
  return ret;
}

Random* Random::_default_random=NULL;

Random* Random::default_random() {
  if (!_default_random) {
    std::string rname("C");
    _default_random = new_random(rname);
  }
  _default_random->ref();
  return _default_random;
}
