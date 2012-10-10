Name:           fmbt
Version:        0.1.1
Release:        1%{?dist}
Summary:        free Model-Based Testing tool

License:        lgpl
URL:            https://github.com/01org/fMBT
Source:		%{name}_%{version}.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  glib2-devel
BuildRequires:  boost-devel
BuildRequires:  ncurses-devel
BuildRequires:  libxml2-devel
BuildRequires:  flex
BuildRequires:  libedit-devel
BuildRequires:  libicu-devel
BuildRequires:  python
BuildRequires:  automake autoconf libtool
%if 0%{?suse_version}
BuildRequires:  libMagick++-devel
BuildRequires:  boost-devel
%else
BuildRequires:  ImageMagick-c++-devel
BuildRequires:  boost-regex
%endif

%if 0%{?suse_version}
Requires:       dbus-1-python
%else
Requires:       dbus-python
%endif

%description
free Model-Based Testing tool automates both generating
and executing tests.

%package core
Summary: Test generator and executor

%description core
Test generator and executor

%package utils
Summary: fMBT visualizing, staticstics, reporting and log utils
Requires: %{name}-python
Requires: %{name}-devel
Requires: python
Requires: graphviz
Requires: gnuplot
Requires: ImageMagick

%description utils
Tools for visualising models, inspecting logs, statistics and reporting

%package coreutils
Summary: GT and AAL models handling
Requires: %{name}-python
Requires: %{name}-devel

%description coreutils
Tools for handling GT and AAL models

%package devel
Summary: C++ headers

%description devel
Headers for building AAL/C++ models and native adapters

%package editor
Summary: Editor
Requires: %{name}-adapters-remote
Requires: %{name}-core
Requires: %{name}-coreutils
Requires: %{name}-utils
Requires: python-pyside

%description editor
fMBT editor

%package python
Summary: fMBT python bindings
Requires: python

%description python
Common Python libraries for various fMBT components

%package adapters-remote
Summary: fMBT remote adapters
Requires: %{name}-python
%if 0%{?suse_version}
Requires:       dbus-1-python
%else
Requires: dbus-python
%endif

%description adapters-remote
Generic remote adapters for running shell script, Python expressions and Javascript

%package adapter-eyenfinger
Summary: fMBT adapter for GUI testing

%if 0%{?suse_version}
Requires: libMagick++5
%else
Requires: ImageMagick-c++
%endif
Requires: ImageMagick
Requires: /usr/bin/xwd
Requires: tesseract
Requires: xautomation

%description adapter-eyenfinger
Proof-of-concept adapter for X11 GUI testing with OCR and icon matching.

%package doc
Summary: fMBT documentation

%description doc
fMBT documentation

%package examples
Summary: fMBT examples

%description examples
various fMBT examples

%prep
%setup -q
./autogen.sh

%build
%configure
make %{?_smp_mflags}


%{!?python_sitelib: %define python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT
rm -f $RPM_BUILD_ROOT/%{_libdir}/python*/site-packages/%{name}/%{name}_cparsers.la
rm -f $RPM_BUILD_ROOT/%{_libdir}/python*/site-packages/eye4graphics.la


%files core
%{_bindir}/%{name}

%files utils
%defattr(-, root, root, -)
%{_bindir}/%{name}-view
%{_bindir}/%{name}-log
%{_bindir}/%{name}-log2lsts
%{_bindir}/%{name}-stats
%{_bindir}/lsts2dot
%{_bindir}/%{name}-ucheck
%{python_sitelib}/%{name}/%{name}-log
%{python_sitelib}/%{name}/%{name}-stats
%{python_sitelib}/%{name}/lsts2dot

%files coreutils
%defattr(-, root, root, -)
%{_bindir}/%{name}-aalc
%{_bindir}/%{name}-aalp
%{_bindir}/%{name}-gt
%{_bindir}/%{name}-parallel
%{python_sitelib}/%{name}/%{name}-gt
%{python_sitelib}/%{name}/%{name}-parallel

%files devel
%defattr(-, root, root, -)
%dir %{_includedir}/%{name}
%{_includedir}/%{name}/*.hh

%files editor
%defattr(-, root, root, -)
%{_bindir}/%{name}-editor
%{_bindir}/%{name}-gteditor
%{python_sitelib}/%{name}/%{name}-editor
%{python_sitelib}/%{name}/%{name}-gteditor

%files python
%defattr(-, root, root, -)
%dir %{python_sitelib}/%{name}
%{python_sitelib}/%{name}.py*
%{python_sitelib}/%{name}/lsts.py*
%{python_sitelib}/%{name}/aalmodel.py*
%{python_sitelib}/%{name}/%{name}parsers.py*
%{python_sitelib}/%{name}/%{name}_config.py*
%dir %{_libdir}/python*/site-packages/%{name}/
%{_libdir}/python*/site-packages/%{name}/%{name}_cparsers.so


%files adapters-remote
%defattr(-, root, root, -)
%{_bindir}/remote_adapter_loader
%{_bindir}/remote_exec.sh
%{_bindir}/remote_pyaal
%{_bindir}/remote_python
%{python_sitelib}/%{name}/remote_pyaal
%{python_sitelib}/%{name}/remote_python
%{python_sitelib}/%{name}web.py*

%files adapter-eyenfinger
%defattr(-, root, root, -)
%{_libdir}/python*/site-packages/eye4graphics.so
%{python_sitelib}/eyenfinger.py*

%files doc
%defattr(-, root, root, -)
%dir %{_datadir}/doc/%{name}/
%doc %{_datadir}/doc/%{name}/README
%doc %{_datadir}/doc/%{name}/*.txt

%files examples
%defattr(-, root, root, -)
%dir %{_datadir}/doc/%{name}/examples
%doc %{_datadir}/doc/%{name}/examples/*

%changelog
