
Name:          bakefile
Version:       0.1.1
Release:       1
Source:        %{name}-%{version}.tar.gz

Prefix:        /usr
Summary:       Cross-platform makefiles generator
License:       GPL
Group:         Development/Other
URL:           http://bakefile.sourceforge.net
Packager:      Vaclav Slavik <vaclav.slavik@matfyz.cz>
BuildRoot:     /var/tmp/%{name}-%{version}-root

Requires:      python >= 2.2.2

%description
Bakefile is makefiles generator that generates native makefiles for
many Unix and Windows compilers.

%prep
%setup -q

%build
./configure --prefix=%{prefix}
%make

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT
%makeinstall

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%doc README THANKS doc/html
%{_bindir}/*
%dir %{_datadir}/bakefile
%{_datadir}/bakefile/*
%dir %{_libdir}/bakefile
%{_libdir}/bakefile/*
%{_datadir}/aclocal/bakefile.m4
%{_mandir}/*/*
