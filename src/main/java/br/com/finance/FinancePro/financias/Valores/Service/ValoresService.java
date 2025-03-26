package br.com.finance.FinancePro.financias.Valores.Service;
import br.com.finance.FinancePro.financias.Valores.Model.ValoresModel;
import br.com.finance.FinancePro.financias.Valores.Repository.ValoresRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class ValoresService {

    private final ValoresRepository valoresRepository;

    public ValoresService(ValoresRepository valoresRepository) {this.valoresRepository = valoresRepository;}

    public List<ValoresModel> getAll() {return valoresRepository.findAll();}
    public ValoresModel save(ValoresModel valoresModel) {return valoresRepository.save(valoresModel);}
    public void delete(Long id) {
        valoresRepository.deleteById(id);}
}
