
Name:          bakefile
Version:       0.2.1
Release:       1
Source:        %{name}-%{version}.tar.gz

Prefix:        /usr
Summary:       Cross-platform makefiles generator
License:       MIT
Group:         Development/Other
URL:           http://bakefile.sourceforge.net
Packager:      Vaclav Slavik <vslavik@fastmail.fm>
BuildRoot:     /var/tmp/%{name}-%{version}-root

Requires:      python >= 2.3.0
BuildRequires: python-devel

%description
Bakefile is makefiles generator that generates native makefiles for
many Unix and Windows compilers.

%prep
%setup -q

%build
./configure --prefix=%{prefix}
make

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT
%makeinstall
ln -sf ../lib/bakefile/bakefile.py $RPM_BUILD_ROOT/usr/bin/bakefile
ln -sf ../lib/bakefile/bakefile_gen.py $RPM_BUILD_ROOT/usr/bin/bakefile_gen

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%doc README THANKS AUTHORS NEWS doc/html
%{_bindir}/*
%dir %{_datadir}/bakefile
%{_datadir}/bakefile/*
%dir %{_libdir}/bakefile
%{_libdir}/bakefile/*
%{_datadir}/aclocal/*.m4
%{_mandir}/*/*
