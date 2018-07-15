###
# This file is part of pysmo.

# psymo is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
# 
# psymo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with pysmo.  If not, see <http://www.gnu.org/licenses/>.
###

"""
Python module for reading/writing SAC files.
"""

from struct import pack, unpack

from sys    import byteorder

__copyright__ = """
Copyright (c) 2012 Simon Lloyd
"""

class sacfile(object):
    """
    Python class for accessing SAC files. Set or read headerfields
    or data.

    Example:
    >>> import sacio
    >>> sacobj = sacio.sacfile('file.sac', 'ro')
    >>> print sacobj.delta
    0.5
    >>> sacobj.delta = 2
    >>> print sacobj.delta
    2
    """

#    Default (undefined) header values
    _headerdefaults = {
        'f':    -12345.0,
        'i':    -12345,
        'l':    -12345,
        '8s':   '-12345  ',
        '16s':  '-12345          '
    }

#    Map of header values
    _headerpars = dict(
        delta=[0,4,'f'],
        depmin=[4,4,'f'],
        depmax=[8,4,'f'],
            scale=[12,4,'f'],
            odelta=[16,4,'f'],
            b=[20,4,'f'],
            e=[24,4,'f'],
            o=[28,4,'f'],
            a=[32,4,'f'],
            fmt=[36,4,'f'],
            t0=[40,4,'f'],
            t1=[44,4,'f'],
            t2=[48,4,'f'],
            t3=[52,4,'f'],
            t4=[56,4,'f'],
            t5=[60,4,'f'],
            t6=[64,4,'f'],
            t7=[68,4,'f'],
            t8=[72,4,'f'],
            t9=[76,4,'f'],
            f=[80,4,'f'],
            resp0=[84,4,'f'],
            resp1=[88,4,'f'],
            resp2=[92,4,'f'],
            resp3=[96,4,'f'],
            resp4=[100,4,'f'],
            resp5=[104,4,'f'],
            resp6=[108,4,'f'],
            resp7=[112,4,'f'],
            resp8=[116,4,'f'],
            resp9=[120,4,'f'],
            stla=[124,4,'f'],
            stlo=[128,4,'f'],
            stel=[132,4,'f'],
            stdp=[136,4,'f'],
            evla=[140,4,'f'],
            evlo=[144,4,'f'],
            evel=[148,4,'f'],
            evdp=[152,4,'f'],
            mag=[156,4,'f'],
            user0=[160,4,'f'],
            user1=[164,4,'f'],
            user2=[168,4,'f'],
            user3=[172,4,'f'],
            user4=[176,4,'f'],
            user5=[180,4,'f'],
            user6=[184,4,'f'],
            user7=[188,4,'f'],
            user8=[192,4,'f'],
            user9=[196,4,'f'],
            dist=[200,4,'f'],
            az=[204,4,'f'],
            baz=[208,4,'f'],
            gcarc=[212,4,'f'],
            sb=[216,4,'f'],
            sdelta=[220,4,'f'],
            depmen=[224,4,'f'],
            cmpaz=[228,4,'f'],
            cmpinc=[232,4,'f'],
            xminimum=[236,4,'f'],
            xmaximum=[240,4,'f'],
            yminimum=[244,4,'f'],
            ymaximum=[248,4,'f'],
            unused6=[252,4,'f'],
            unused7=[256,4,'f'],
            unused8=[260,4,'f'],
            unused9=[264,4,'f'],
            unused10=[268,4,'f'],
            unused11=[272,4,'f'],
            unused12=[276,4,'f'],
            nzyear=[280,4,'i'],
            nzjday=[284,4,'i'],
            nzhour=[288,4,'i'],
            nzmin=[292,4,'i'],
            nzsec=[296,4,'i'],
            nzmsec=[300,4,'i'],
            nvhdr=[304,4,'i'],
            norid=[308,4,'i'],
            nevid=[312,4,'i'],
            npts=[316,4,'i'],
            nsnpts=[320,4,'i'],
            nwfid=[324,4,'i'],
            nxsize=[328,4,'i'],
            nysize=[332,4,'i'],
            unused15=[336,4,'i'],
            iftype=[340,4,'i'],
            idep=[344,4,'i'],
            iztype=[348,4,'i'],
            unused16=[352,4,'i'],
            iinst=[356,4,'i'],
            istreg=[360,4,'i'],
            ievreg=[364,4,'i'],
            ievtyp=[368,4,'i'],
            iqual=[372,4,'i'],
            isynth=[376,4,'i'],
            imagtyp=[380,4,'i'],
            imagsrc=[384,4,'i'],
            unused19=[388,4,'i'],
            unused20=[392,4,'i'],
            unused21=[396,4,'i'],
            unused22=[400,4,'l'],
            unused23=[404,4,'i'],
            unused24=[408,4,'i'],
            unused25=[412,4,'i'],
            unused26=[416,4,'i'],
            leven=[420,4,'i'],
            lpspol=[424,4,'i'],
            lovrok=[428,4,'i'],
            lcalda=[432,4,'i'],
            unused27=[436,4,'i'],
            kstnm=[440,8,'8s'],
            kevnm=[448,16,'16s'],
            khole=[464,8,'8s'],
            ko=[472,8,'8s'],
            ka=[480,8,'8s'],
            kt0=[488,8,'8s'],
            kt1=[496,8,'8s'],
            kt2=[504,8,'8s'],
            kt3=[512,8,'8s'],
            kt4=[520,8,'8s'],
            kt5=[528,8,'8s'],
            kt6=[536,8,'8s'],
            kt7=[544,8,'8s'],
            kt8=[552,8,'8s'],
            kt9=[560,8,'8s'],
            kf=[568,8,'8s'],
            kuser0=[576,8,'8s'],
            kuser1=[584,8,'8s'],
            kuser2=[592,8,'8s'],
            kcmpnm=[600,8,'8s'],
            knetwk=[608,8,'8s'],
            kdatrd=[616,8,'8s'],
            kinst=[624,8,'8s']
    )

#    Define enumerated header fields
    _enumlist = (_headerdefaults['i'], 'time', 'rlim', 'amph', 'xy',
            'unkn', 'disp', 'vel', 'acc', 'b', 'day', 'o', 'a',
            't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8',
            't9', 'radnv', 'tannv', 'radev', 'tanev', 'north',
            'east', 'horza', 'down', 'up', 'lllbb', 'wwsn1',
            'wwsn2', 'hglp', 'sro', 'nucl', 'pren', 'postn',
            'quake', 'preq', 'postq', 'chem', 'other', 'good',
            'glch', 'drop', 'lowsn', 'rldta', 'volts', 'xyz',
            'mb', 'ms', 'ml', 'mw', 'md', 'mx', 'neic', 'pde',
            'isc', 'reb', 'usgs', 'brk', 'caltech', 'llnl',
            'evloc', 'jsop', 'user', 'unknown', 'qb', 'qb1',
            'qb2', 'qbx', 'qmt', 'eq', 'eq1', 'eq2', 'me',
            'ex', 'nu', 'nc', 'o_', 'l', 'r', 't', 'u')

#   Dictionary for looking up values of enumerated items
    _index = [-12345]
    _index.extend(list(range(1, 87)))
    enumdict = dict(list(zip(_enumlist, _index)))

#   Headerfields using enumerated items and legal values
    _enumhead = dict(
        iftype= ('time', 'rlim', 'amph', 'xy', 'xyz', _headerdefaults['i']),
        idep=   ('unkn', 'disp', 'vel', 'volts', 'acc', _headerdefaults['i']),
        iztype= ('unkn', 'b', 'day', 'o', 'a', 'at1', 'at2', 'at3', 'at4',
             'at5', 'at6','at7', 'at8','at9', _headerdefaults['i']),
        iinst=  ('', _headerdefaults['i']),
        istreg= ('', _headerdefaults['i']),
        ievreg= ('', _headerdefaults['i']),
        imagtype=('mb', 'ms', 'ml', 'mw', 'md', 'mx', _headerdefaults['i']),
        imagsrc=('neic', 'pde', 'isc', 'reb', 'usgs', 'brk', 'caltech',
             'llnl', 'evloc', 'jsop', 'user', 'unknown', _headerdefaults['i']),
        ievtyp= ('unkn', 'nucl', 'pren', 'postn', 'quake', 'preq', 'postq',
                 'chem', 'qb', 'qb1', 'qb2', 'qbx', 'qbmt', 'eq', 'eq1', 'eq2',
                 'me', 'me', 'ex', 'nu', 'nc', 'o_', 'l', 'r', 't', 'u',
                 'other', _headerdefaults['i']),
        iqual=  ('good', 'glch', 'drop', 'lowsn', 'other',
                 _headerdefaults['i']),
        isynth= ('rldta', _headerdefaults['i'])
    )

    _attributes = ['fh', 'mode', 'filename', '_file_byteorder',
                   '_machine_byteorder']

    def __init__(self, filename, mode='ro', **kwargs):
        """
        Open the SAC file with mode read "ro", write "rw" or new "new".
        """
        if mode not in ('ro', 'rw', 'new'):
            raise ValueError('mode=%s not in (ro, rw, new)' % mode)
        else:
            setattr(self, 'mode', mode)
            setattr(self, 'filename', filename)
            self.__get_machine_byteorder()

        if mode == 'ro':
            setattr(self, 'fh', open(filename, 'rb'))
            self.__get_file_byteorder()
        elif mode == 'rw':
            f = open(filename, 'r+b')
            setattr(self, 'fh', f)
            self.__get_file_byteorder()
            if self._file_byteorder != self._machine_byteorder:
                self.__convert_file_byteorder(self._machine_byteorder)
            self._file_byteorder = self._machine_byteorder
        elif mode == 'new':
            setattr(self, 'fh', open(filename, 'w+b'))
            self._file_byteorder = self._machine_byteorder
            self.__setupnew()
        for name, value in list(kwargs.items()):
            setattr(self, name, value)

    def __get_file_byteorder(self):
        """
        Check the byte order of a SAC file and store it in self._file_byteorder.
        """
        # seek position of 'unused12', which should be -12345.0
        self.fh.seek(276)
        if unpack('>f', (self.fh.read(4)))[-1] == -12345.0:
            self._file_byteorder = '>'
        else:
            self._file_byteorder = '<'
    
    def __convert_file_byteorder(self, byteorder):
        """
        Change the file byte order to the system byte order.
        This works (or should work), because we read the file
        in the detected file byteorder, and write in the 
        machine byteorder.
        """
        # read the data first and save it 
        try:
            data = self.data3D
        except:
            try:
                data = self.data2D
            except:
                data = self.data
        # switch byteorder for all headervariables
        for headerpar in list(self._headerpars.keys()):
            cmd = 'self.%s = self.%s' % (headerpar, headerpar)
            try:
                exec(cmd)
            # we will get an error if the headerfield is undefined in 
            # the SAC file
            except ValueError:
                cmd = 'self.%s = default' % headerpar
                exec(cmd)
        # update self._file_byteorder, which should now be the same
        # as the machine byteorder
        self.__get_file_byteorder()
        # now that self._file_byteorder is set we can write the data to the file
        try:
            self.data3D = data
        except:
            try:
                self.data2D = data
            except:
                self.data = data

    def __get_machine_byteorder(self):
        """
        Check the system byte order and store it in self._machine_byteorder.
        """
        if byteorder == 'little':
            self._machine_byteorder = '<'
        else:
            self._machine_byteorder = '>'

    def __del__(self):
        self.fh.close()

    def close(self):
        self.__del__()

    def __getattr__(self, name):
        if name in self._headerpars:
            return self.__readhead(name)
        elif name == 'data':
            return self.__readdata(1)
        elif name == 'data2D':
            return self.__readdata(2)
        elif name == 'data3D':
            return self.__readdata(3)
        else:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in self._headerpars:
            self.__writehead(name, value)
        elif name == 'data':
            self.__writedata(value, 1)
            self.__sanitycheck()
        elif name == 'data2D':
            self.__writedata(value, 2)
        elif name == 'data3D':
            self.__writedata(value, 3)
        elif name in self._attributes:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(name)

    def __readhead(self, headerfield):
        """
        Read header field from SAC file. Enumerated
        header fields are automatically translated.
        """
        pos, length, htype = self._headerpars[headerfield]
        self.fh.seek(pos)
        content = self.fh.read(length)
        headervalue = unpack(self._file_byteorder+htype, content)[0]
        # py2 ignores difference between str '...' and bytes b'...'
        # need to decode in py3 
        # Cannot write decoded though. Decode outside of here.
        #if type(headervalue) is bytes:
        #    headervalue = headervalue.decode()
        if headervalue == self._headerdefaults[htype]:
            raise ValueError('Header %s is undefined' % headerfield)
        if headerfield in self._enumhead:
            return self._enumlist[headervalue]
        else:
            return headervalue

    def __writehead(self, headerfield, headervalue):
        """
        Write header field to SAC file. Enumerated
        header fields are automatically translated.
        """
        if self.mode == 'ro':
            raise IOError('File %s is readonly' % self.filename)
        pos, length, htype = self._headerpars[headerfield]
        if headerfield in self._enumhead:
            if headervalue in self._enumhead[headerfield]:
                headervalue = self.enumdict[headervalue]
            else:
                raise ValueError('%s not an allowed value for %s' % \
                (headervalue, headerfield))
        #print(htype, headervalue, headerfield)
        headervalue = pack(htype, headervalue)
        self.fh.seek(pos)
        self.fh.write(headervalue)

    def __readdata(self, dimensions):
        """
        Read 1D, 2D or 3D data from SAC file.
        """
        data  = []
        format = self._file_byteorder + str(self.npts) + 'f'
        length = self.npts * 4
        self.fh.seek(632)
        content  = self.fh.read(length)
        sacdata1 = unpack(format, content)
        if dimensions >= 2:
            content  = self.fh.read(length)
            sacdata2 = unpack(format, content)
        if dimensions == 3:
            content  = self.fh.read(length)
            sacdata3 = unpack(format, content)
        if dimensions == 1:
            for x1 in sacdata1:
                data.append(x1)
        elif dimensions == 2:
            for x1, x2 in zip(sacdata1, sacdata2):
                data.append((x1, x2))
        elif dimensions == 3:
            for x1, x2, x3 in zip(sacdata1, sacdata2, sacdata3):
                data.append((x1, x2, x3))
        return data

    def __writedata(self, data, dimensions,):
        """
        Write 1D, 2D or 3D data to SAC file.
        """
        if self.mode == 'ro':
            raise IOError('File %s is readonly' % self.filename)
        self.npts = len(data)
        self.fh.truncate(632)
        self.fh.seek(632)
        data1 = []
        data2 = []
        data3 = []
        for x in data:
            if dimensions == 1:
                data1.append(x)
            elif dimensions >= 2:
                data1.append(x[0])
                data2.append(x[1])
            if dimensions == 3:
                data3.append(x[2])
        data1.extend(data2)
        data1.extend(data3)
        for x in data1:
            self.fh.write(pack('f', x))

    def __setupnew(self):
        """
        Setup new file and set required header fields to sane values.
        """
        for headerfield in list(self._headerpars.keys()):
            pos, length, htype = self._headerpars[headerfield]
            default = self._headerdefaults[htype]
            self.__writehead(headerfield, default)
        self.npts = 0
        self.nvhdr = 6
        self.b = 0
        self.e = 0
        self.iftype = 'time'
        self.leven = 1
        self.delta = 1

    def __sanitycheck(self):
        """
        Calculate and set header fields that describe the data.
        """
        self.e = self.b + (self.npts - 1) * self.delta
        self.depmin = min(self.data)
        self.depmax = max(self.data)
        self.depmen = sum(self.data)/self.npts
