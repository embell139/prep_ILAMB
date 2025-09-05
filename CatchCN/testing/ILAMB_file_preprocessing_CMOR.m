clc
clear all
close all

exp_path = '/discover/nobackup/projects/geoscm/fzeng/Catchment-CN40_9km/GHG_center_data_milan/';
exp_name = 'GEOSldas_CN40_9km';
exp_res = 'SMAP_EASEv2_M09_GLOBAL';

save_path = [exp_path exp_name '_ILAMB'];
save_name = [exp_name '_ILAMB'];

start_year = 2000;
stop_year = 2011;

leapYears = 1980:4:2022;
monthLength_nly = [31 28 31 30 31 30 31 31 30 31 30 31];
monthLength_ly = [31 29 31 30 31 30 31 31 30 31 30 31];

% create save directory

cmd_mkdir = ['mkdir ' save_path];
[status,cmdout] = system(cmd_mkdir)

mat_index = 0;

for y = start_year:stop_year

    y_str = num2str(y,'%04i')

    % define month length based on leap year status
    if sum(y==leapYears)>0
       monthLength = monthLength_ly;
    else
       monthLength = monthLength_nly;
    end

    for m = 1:12

        mat_index = mat_index + 1;

        m_str = num2str(m,'%02i');

        % define file names

        exp_read_file = [exp_path exp_name '/output/' exp_res '/cat/ens0000/Y' y_str ...
                         '/M' m_str '/' exp_name '.tavg24_1d_lnd_Nt.monthly.' y_str m_str '.nc4'];

        exp_file_name = [exp_name '.tavg24_1d_lnd_Nt.monthly.' y_str m_str '.nc4'];

        if (mat_index == 1)

           lat_vec = ncread(exp_read_file,'lat');
           lon_vec = ncread(exp_read_file,'lon');

           exp_gpp = NaN*ones(length(lat_vec),(stop_year-start_year+1)*12);
           exp_time = ones((stop_year-start_year+1)*12);
        end 


        % read data to be converted

        exp_gpp(:,mat_index) = ncread(exp_read_file,'CNGPP');

    end
end

% convert data 

save_gpp = exp_gpp*1000*86400;          % kgC m^-2 s^-1 => gC m^-2 day^-1
save_gpp = single(save_gpp);

% write new data to file

nccreate(save_file,"gpp","Dimensions",{"tile",size(save_gpp,1),"time",size(save_gpp,2)},"FillValue",1e15);
ncwrite(save_file,'gpp',save_gpp);
ncwriteatt(save_file,'gpp',"long_name","CN_gross_primary_production");
ncwriteatt(save_file,'gpp',"units","gC m^-2 day^-1");

% convert variables that are written as 'double' to new file to 'float'

cmd_ncap = ['ncap2 -O -s ''gpp=float(gpp)'' ' save_file ' ' save_file];
[status,cmdout] = system(cmd_ncap)


